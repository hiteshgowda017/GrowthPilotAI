import os
import json
import asyncio
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import AsyncGroq
from dotenv import load_dotenv
from ddgs import DDGS

# Support both Render layouts:
# 1) Root Directory = backend -> "uvicorn main:app"
# 2) Repository root -> "uvicorn backend.main:app"
try:
    from .research_utils import summarize_fallback, rank_candidates, target_evidence, candidate_verification
except ImportError:
    from research_utils import summarize_fallback, rank_candidates, target_evidence, candidate_verification

load_dotenv()

app = FastAPI(title="GrowthPilot AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    business_name: str = Field(..., min_length=1)
    website: str = ""
    industry: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)


class GrowthPilotEngine:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to the Render environment variables."
            )

        self.client = AsyncGroq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        # Browser Search is explicitly supported by GPT-OSS models.
        self.browser_model = os.getenv("GROQ_BROWSER_MODEL", "openai/gpt-oss-20b")
        # Disabled by default so DDGS remains the dependable live-research
        # path and a Groq browser-search quota issue cannot break the audit.
        self.use_browser_research = (
            os.getenv("GROQ_BROWSER_RESEARCH", "false").strip().lower()
            == "true"
        )

    async def robust_search(
        self,
        query: str,
        max_results: int = 6,
        retries: int = 2,
        region: str = "in-en",
    ) -> str:
        """Run one resilient DDGS metasearch query."""
        for attempt in range(1, retries + 1):
            try:
                print(f"[SEARCH] region={region} query={query}")

                def do_search():
                    with DDGS() as search:
                        return list(
                            search.text(
                                query,
                                region=region,
                                safesearch="moderate",
                                max_results=max_results,
                                backend="auto",
                            )
                        )

                results = await asyncio.to_thread(do_search)

                if results:
                    return "\n".join(
                        f"SEARCH QUERY: {query}\n"
                        f"- {r.get('title', '')}\n"
                        f"  {r.get('body', '')}\n"
                        f"  Source: {r.get('href', '')}"
                        for r in results
                    )

            except Exception as exc:
                print(
                    f"[SEARCH WARNING] attempt={attempt} "
                    f"query={query}: {type(exc).__name__}: {exc}"
                )

            if attempt < retries:
                await asyncio.sleep(1)

        return ""

    async def browser_research(self, prompt: str) -> str:
        """Run one Groq server-side browser research session."""
        try:
            print("[BROWSER] Starting live browser research...")
            response = await self.client.chat.completions.create(
                model=self.browser_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are GrowthPilot live web research. "
                            "You MUST search the live web before answering. "
                            "Use multiple relevant sources. Return concrete "
                            "names, locations, services, dates and URLs when available. "
                            "Never invent missing facts."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                reasoning_effort="low",
                include_reasoning=False,
                tool_choice="required",
                tools=[{"type": "browser_search"}],
                max_completion_tokens=7000,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
            print("[BROWSER WARNING] Search returned no final content.")
        except Exception as exc:
            print(f"[BROWSER ERROR] {type(exc).__name__}: {exc}")
        return ""


    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.4,
    ) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are GrowthPilot AI. Return only valid JSON "
                            "when a JSON response is requested."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                reasoning_effort="low",
                include_reasoning=False,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_completion_tokens=6500,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Groq returned an empty response.")

            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Groq returned JSON that is not an object.")

            return data

        except json.JSONDecodeError as exc:
            print(f"[JSON ERROR] Invalid JSON from Groq: {exc}")
            raise HTTPException(
                status_code=502,
                detail="AI returned an invalid JSON response.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc)
            print(f"[GROQ ERROR] {type(exc).__name__}: {message}")

            # Preserve 429 so the visibility audit can fall back to its
            # live DDGS evidence instead of failing the entire request.
            if "429" in message or "rate_limit_exceeded" in message.lower():
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Groq rate limit reached. GrowthPilot is using "
                        "the live DDGS research fallback for this audit."
                    ),
                )

            raise HTTPException(
                status_code=502,
                detail=f"Groq AI request failed: {message}",
            )


    @staticmethod
    def clean_domain(website: str) -> str:
        if not website.strip():
            return ""

        value = website.strip()
        if "://" not in value:
            value = "https://" + value

        parsed = urlparse(value)
        return parsed.netloc or parsed.path.split("/")[0]

    async def run_full_analysis(
        self,
        name: str,
        website: str,
        industry: str,
        location: str,
        goal: str,
    ) -> dict:
        """Evidence-first executive growth analysis."""
        print(f"=== GROWTHPILOT ANALYSIS: {name.upper()} ===")

        domain = self.clean_domain(website)
        # Search the actual business/entity first. Industry and location are
        # used as constraints, not as the primary search identity.
        target_queries = [
            f'"{name}" "{location}" official website',
            f'"{name}" "{location}" {industry} services',
            f'"{name}" "{location}" LinkedIn',
            f'"{name}" "{location}" reviews',
            f'"{name}" competitors "{location}"',
            f'"{name}" alternatives "{location}"',
            f'"{name}" similar companies "{location}"',
        ]
        if domain:
            target_queries.extend([
                f'site:{domain} {name} services',
                f'site:{domain} {name} products solutions',
            ])

        # Competitor research is anchored to the actual target and then
        # broadened to independent/local discovery.
        local_queries = [
            # Exact-business discovery comes first. Industry/location are constraints.
            f'"{name}" "{location}" competitors',
            f'"{name}" "{location}" alternatives',
            f'"{name}" "{location}" similar companies',
            f'"{name}" "{location}" competitors "{industry}"',
            # Independent discovery remains tied to the same target context.
            f'"{industry}" companies "{location}" "{name}"',
            f'"{industry}" providers "{location}" "{name}"',
            f'"{industry}" services "{location}" "{name}"',
        ]

        global_queries = [
            f'"{name}" global competitors "{industry}"',
            f'"{name}" international competitors "{industry}"',
            f'"{name}" global alternatives "{industry}"',
            f'"{name}" similar companies worldwide "{industry}"',
            f'"{industry}" companies similar to "{name}"',
            f'"{industry}" global companies similar to "{name}"',
        ]

        review_queries = [
            f'"{name}" "{location}" reviews',
            f'"{name}" "{location}" complaints',
            f'"{name}" "{location}" customer experience',
        ]

        async def collect(queries: list[str], region: str) -> str:
            chunks = []
            for query in queries:
                result = await self.robust_search(query, max_results=6, retries=1, region=region)
                if result:
                    chunks.append(result)
            return "\n\n".join(chunks)

        target_data, local_data, global_data, review_data = await asyncio.gather(
            collect(target_queries, "in-en"),
            collect(local_queries, "in-en"),
            collect(global_queries, "us-en"),
            collect(review_queries, "in-en"),
        )

        local_candidates = rank_candidates(local_data, industry, location, "local", name, 8)
        global_candidates = rank_candidates(global_data, industry, location, "global", name, 8)
        target_info = target_evidence(target_data, name, industry, location)

        # One synthesis call turns the verified live-search dossier into a
        # detailed competitor intelligence report and an executable strategy.
        prompt = f"""
You are GrowthPilot's senior competitive-intelligence and strategy analyst.

Your job is NOT to write a generic business plan. Build a research-backed
competitive intelligence dossier for the exact business entered by the user.

========================
INPUT BUSINESS
========================
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}
Business Goal: {goal}

========================
RESEARCH METHOD
========================
Live search was performed with DDGS. Deterministic filters were applied before
this prompt to remove obvious non-business/noise results and to check industry,
location and target-name relevance.

Treat the supplied evidence as the source of truth.
Do NOT use your own general knowledge to fill missing facts.

========================
TARGET BUSINESS EVIDENCE
========================
{json.dumps(target_info, indent=2)}

========================
LOCAL COMPETITOR CANDIDATES
========================
{json.dumps(local_candidates, indent=2)}

========================
GLOBAL COMPETITOR CANDIDATES
========================
{json.dumps(global_candidates, indent=2)}

========================
RAW LIVE TARGET EVIDENCE
========================
{target_data[:9000]}

========================
RAW LIVE REVIEW EVIDENCE
========================
{review_data[:6000]}

========================
RAW LIVE LOCAL EVIDENCE
========================
{local_data[:11000]}

========================
RAW LIVE GLOBAL EVIDENCE
========================
{global_data[:9000]}

================================================
NON-NEGOTIABLE ACCURACY CONTRACT
================================================
1. The target business is "{name}". Never replace it with an industry category.
2. A competitor must be a real business/company, not a topic, definition,
   movie, book, person, article, generic directory category or acronym meaning.
3. A local competitor must have evidence connecting the business to {location}
   or the immediate local market AND evidence that it offers {industry}.
4. A global competitor must have evidence that it is a real company and relevant
   to {industry}. "Top company" search-result wording alone is not enough.
5. Never treat Wikipedia/YouTube/IMDb/Britannica/Microsoft generic definition
   pages as competitors.
6. Search snippets are leads, not proof. Prefer official company pages and
   reputable business profiles when available.
7. Directory listings may establish that a business exists, but do not claim
   quality, market share, revenue, leadership or superiority from a directory.
8. Never invent services, clients, prices, locations, weaknesses, rankings,
   market share, reviews or business strategies.
9. If evidence is insufficient, explicitly say "Not verified" or "Insufficient
   evidence" instead of guessing.
10. Never recommend a new country, market or customer segment unless the supplied
    evidence gives a concrete reason for it.
11. Scores are evidence-based estimates of DIGITAL VISIBILITY, not audited
    market share or business quality.
12. Do not rank a company as "number 1" unless the supplied evidence genuinely
    supports a defensible ranking. Otherwise say "Relative position not verified."
13. Prefer 2-5 highly relevant competitors over 10 weak matches.
14. Every competitor profile must explain WHY it was included and list its
    supporting source URLs from the supplied evidence.
15. Recommendations must map to a specific finding in this dossier.

================================================
REPORT OBJECTIVE
================================================
Produce a report that a founder/manager could actually use to understand:
- what the target business is doing online,
- who is genuinely competing for the same customers,
- how each relevant competitor is positioned,
- where the target appears exposed,
- what opportunities are supported by evidence,
- and exactly what to execute over the next 180 days.

The report must distinguish:
VERIFIED FINDING / RESEARCH INFERENCE / UNKNOWN.

Do not pad the report with generic marketing advice.

================================================
REQUIRED REPORT STRUCTURE
================================================
Write detailed Markdown using EXACTLY these phases:

# GrowthPilot Competitive Intelligence & Strategic Growth Report

## Phase I: Executive Intelligence Brief
Include:
- Target business
- Research date/context
- Evidence coverage
- 5-8 key findings
- 3 most important strategic implications
- Clear list of what could NOT be verified

## Phase II: Target Business Digital & Market Audit
Create a compact table:
Area | Verified Evidence | Signal | Confidence
Cover:
- website/official presence
- service/product positioning
- local discoverability
- social/professional presence
- reviews/reputation where evidence exists
- search visibility
- market positioning
Do not invent missing metrics.

## Phase III: Local Competitor Intelligence
For EACH verified local competitor:
### [Competitor Name]
Include:
- Why it qualifies as a competitor
- Location evidence
- Industry/service evidence
- Digital visibility evidence
- Positioning observed from sources
- Observable strength
- Observable weakness/gap (only if supported)
- Threat/opportunity relevance to the target
- Source URLs

Then provide a comparison table:
Competitor | Local relevance | Service overlap | Digital signal | Evidence confidence | Strategic implication

## Phase IV: Global / Macro Competitor Intelligence
Use the same structure for genuinely relevant international companies.
Do NOT confuse "large company" with "competitor".
Explain whether each is a direct competitor, adjacent competitor, or market benchmark.

Then provide:
Company | Relevance type | Evidence | Digital signal | Strategic lesson

## Phase V: Competitive Positioning & Gap Analysis
Build a finding matrix:
Finding | Target evidence | Competitor evidence | Gap | Confidence
Separate:
- Verified gaps
- Probable opportunities
- Unknowns requiring validation

## Phase VI: Digital Visibility Strategy
Give specific actions based on observed evidence for:
- website/search discoverability
- local visibility
- professional/social presence
- content authority
- reviews/reputation
- AI/search discoverability
Do NOT say merely "improve SEO" or "use AI". Specify what should be changed and why.

## Phase VII: Strategic Growth Opportunities
Provide 5-7 opportunities maximum.
For each:
Opportunity | Evidence | Why now | Expected business effect | Effort | Priority
Do not invent financial forecasts.

## Phase VIII: 30 / 60 / 90 / 180-Day Execution Plan
Create a practical roadmap.

0-30 days:
- exact actions
- owner/role
- output
- KPI

31-60 days:
- exact actions
- owner/role
- output
- KPI

61-90 days:
- exact actions
- owner/role
- output
- KPI

91-180 days:
- exact actions
- owner/role
- output
- KPI

Only use actions justified by the evidence. Mark validation-dependent actions clearly.

## Phase IX: Measurement Framework
Define 8-12 measurable KPIs.
For each:
KPI | Baseline | Target direction | Measurement method | Review frequency

If baseline is unavailable, write "Baseline required" rather than inventing a number.

## Phase X: Risks, Unknowns & Next Research
List:
- evidence gaps
- assumptions
- risks
- exact searches/data that should be performed next
- what could change the strategy

## Phase XI: Executive Action List
Finish with the 10 highest-value actions in execution order.
Each action must reference the finding that justifies it.

================================================
METRICS
================================================
Return metrics separately:
- market_rank: use "Relative position not verified" unless defensible evidence exists
- ai_visibility_score: 0-100 estimate from observable search/AI visibility evidence
- vulnerability_score: 0-100 estimate from verified competitive gaps
- top_opportunity: one concise evidence-backed opportunity

================================================
JSON OUTPUT
================================================
Return ONLY valid JSON in this exact shape:
{{
  "metrics": {{
    "market_rank": "Relative position not verified",
    "ai_visibility_score": 0,
    "vulnerability_score": 0,
    "top_opportunity": "Insufficient verified evidence"
  }},
  "report_markdown": "FULL DETAILED REPORT IN MARKDOWN"
}}
"""

        print("[PHASE 4] Sending filtered live research to Groq...")
        try:
            return await self.generate_json(prompt, temperature=0.05)
        except HTTPException as exc:
            if exc.status_code == 429:
                return {
                    "metrics": {
                        "market_rank": "AI synthesis unavailable — live evidence collected",
                        "ai_visibility_score": "Not calculated",
                        "vulnerability_score": "Not calculated",
                        "top_opportunity": "Review the verified competitor evidence in the Visibility Audit"
                    },
                    "report_markdown": (
                        "# GrowthPilot Executive Intelligence Report\n\n"
                        "## Phase I: Live Research Collected\n"
                        "Live target, local, global and review evidence was collected, "
                        "but AI synthesis is currently rate-limited.\n\n"
                        "## Phase II: Verified Research\n"
                        f"Target: {json.dumps(target_info)}\n\n"
                        f"Local candidates: {json.dumps(local_candidates[:5])}\n\n"
                        f"Global candidates: {json.dumps(global_candidates[:5])}\n\n"
                        "## Phase III: Next Validation Step\n"
                        "Run AI synthesis again when the Groq token window is available."
                    )
                }
            raise
    async def verify_competitor_candidates(
        self,
        candidates: list[dict],
        industry: str,
        location: str,
        role: str,
        target_name: str,
    ) -> list[dict]:
        """Re-search each candidate by exact entity name before exposing it."""
        semaphore = asyncio.Semaphore(3)

        async def verify_one(candidate: dict) -> dict | None:
            candidate_name = str(candidate.get("name", "")).strip()
            if not candidate_name:
                return None

            # Each candidate gets independent, exact-name verification. The
            # discovery query is never treated as proof by itself.
            if role == "local":
                queries = [
                    f'"{candidate_name}" "{location}" "{industry}"',
                    f'"{candidate_name}" "{location}" official',
                    f'"{candidate_name}" "{industry}" services "{location}"',
                ]
            else:
                queries = [
                    f'"{candidate_name}" "{industry}"',
                    f'"{candidate_name}" official',
                    f'"{candidate_name}" "{industry}" services',
                ]

            async with semaphore:
                raw_parts = []
                for query in queries:
                    result = await self.robust_search(
                        query, max_results=5, retries=1,
                        region="in-en" if role == "local" else "wt-wt"
                    )
                    if result:
                        raw_parts.append(result)

            raw = "\n\n".join(raw_parts)
            verified = candidate_verification(
                raw,
                candidate_name,
                industry,
                location,
                role,
                target_name,
            )
            if not verified:
                print(f"[VERIFY] Rejected {role} candidate: {candidate_name}")
                return None

            # Preserve the original discovery score as context but make the
            # verification score the displayed evidence score.
            return {
                **candidate,
                **verified,
                "score": verified["verification_score"],
                "evidence_summary": verified["evidence_summary"],
                "sources": verified["sources"],
            }

        verified = await asyncio.gather(*(verify_one(c) for c in candidates[:6]))
        return [x for x in verified if x is not None][:5]

    async def run_visibility_audit(
        self,
        name: str,
        website: str,
        industry: str,
        location: str,
    ) -> dict:
        """Deep live visibility audit driven by the user's five inputs."""
        print(f"=== VISIBILITY AUDIT: {name.upper()} | {industry} | {location} ===")

        domain = self.clean_domain(website)

        # Stage 1: establish the exact target entity before looking for competitors.
        target_queries = [
            f'"{name}"',
            f'"{name}" "{location}"',
            f'"{name}" "{industry}"',
            f'"{name}" official',
            f'"{name}" services',
            f'"{name}" reviews',
            f'"{name}" LinkedIn',
        ]
        if domain:
            target_queries.extend([
                f'site:{domain}',
                f'site:{domain} services',
            ])

        # Stage 2: competitor discovery is anchored to the exact target,
        # with industry/location acting as constraints.
        local_queries = [
            f'"{name}" competitors "{location}"',
            f'"{name}" alternatives "{location}"',
            f'"{name}" similar companies "{location}"',
            f'"{name}" competitors "{industry}" "{location}"',
            f'"{industry}" companies "{location}" "{name}"',
            f'"{industry}" providers "{location}" "{name}"',
            f'"{industry}" services "{location}" "{name}"',
        ]

        global_queries = [
            f'"{name}" global competitors "{industry}"',
            f'"{name}" international competitors "{industry}"',
            f'"{name}" global alternatives "{industry}"',
            f'"{name}" similar companies "{industry}"',
            f'"{industry}" companies similar to "{name}"',
            f'"{industry}" global companies similar to "{name}"',
        ]

        async def collect(queries: list[str], region: str) -> str:
            chunks = []
            for query in queries:
                result = await self.robust_search(
                    query, max_results=6, retries=1, region=region
                )
                if result:
                    chunks.append(result)
            return "\n\n".join(chunks)

        target_raw, local_raw, global_raw = await asyncio.gather(
            collect(target_queries, "in-en"),
            collect(local_queries, "in-en"),
            collect(global_queries, "us-en"),
        )

        # Deterministic evidence gate. This is also the no-AI emergency path.
        fallback = summarize_fallback(
            name, industry, location, target_raw, local_raw, global_raw
        )

        verified_local = await self.verify_competitor_candidates(
            fallback.get("local_competitors", []),
            industry,
            location,
            "local",
            name,
        )
        verified_global = await self.verify_competitor_candidates(
            fallback.get("market_leaders", []),
            industry,
            location,
            "global",
            name,
        )
        fallback["local_competitors"] = verified_local
        fallback["market_leaders"] = verified_global
        fallback["research_coverage"]["local_candidates"] = len(verified_local)
        fallback["research_coverage"]["global_candidates"] = len(verified_global)

        live_evidence = (
            f"TARGET DDGS:\n{target_raw}\n\n"
            f"LOCAL DDGS:\n{local_raw}\n\n"
            f"GLOBAL DDGS:\n{global_raw}"
        )

        if not live_evidence.strip():
            return fallback

        synthesis_prompt = f"""
You are GrowthPilot's senior LIVE DIGITAL VISIBILITY and COMPETITIVE-INTELLIGENCE analyst.

USER RESEARCH INPUTS
====================
Target Corporation Name: {name}
Production Domain URL: {website or "Not provided"}
Market Vertical / Sector: {industry}
Geographic Vector Hub: {location}

These five inputs define the research scope. The target must remain the exact
business named above. Industry and location are constraints, not substitutes
for the target identity.

LIVE DDGS EVIDENCE
==================
{live_evidence[:60000]}

STRICT ENTITY VERIFICATION
==========================
A LOCAL competitor is valid only if BOTH the discovery evidence
AND the fresh exact-name verification evidence support:
1. a real operating company/business,
2. meaningful service/product overlap with "{industry}",
3. a connection to "{location}" or its immediate local market.

A GLOBAL competitor is valid only if BOTH the discovery evidence
AND the fresh exact-name verification evidence support:
1. a real operating company,
2. meaningful relevance to "{industry}",
3. a credible relationship to the target's market:
   Direct competitor, Adjacent competitor, or Market benchmark.

Reject:
- Wikipedia/definition pages
- YouTube/videos
- films/movies/books/novels
- actors/people
- job listings/career pages
- generic industry listicles
- directory category pages
- unrelated acronym meanings
- generic "software", "IT", "technology" pages

A directory can be used only as discovery evidence; it is not enough to claim
market leadership, quality, revenue, market share or superiority.

TARGET VERIFICATION
===================
Verify that the results actually refer to "{name}".
When "{website}" is provided, matching-domain evidence is strong.
Do not claim that a domain is officially owned by the target unless the evidence
supports that conclusion.

LIVE VISIBILITY INDEX
=====================
Produce a 0-100 OBSERVABLE LIVE WEB VISIBILITY score using only supplied evidence:
- repeated appearance across distinct searches,
- breadth of relevant results,
- diversity of source domains,
- official-domain presence,
- local discoverability,
- industry relevance.

This score is NOT market share, revenue, customer count, valuation, business
quality, or a Google ranking position.

OUTPUT RULES
============
- Maximum 5 local competitors and 5 global competitors.
- Fewer is better than wrong.
- Every returned competitor requires an evidence summary and source URLs from
  the supplied evidence.
- If weakness is not evidenced, write "Not verified".
- If market rank is not defensible, write "Relative position not verified".
- Do not invent missing facts.
- Return ONLY valid JSON.

SCHEMA
======
{{
  "target": {{
    "name": "{name}",
    "score": 0,
    "evidence_level": "High",
    "evidence_summary": "What the live evidence verifies",
    "sources": []
  }},
  "local_competitors": [],
  "market_leaders": [],
  "insight_summary": "Evidence-based diagnostic only",
  "research_coverage": {{
    "status": "live_ddgs",
    "provider": "DDGS",
    "target_results": 0,
    "local_results": 0,
    "global_results": 0,
    "local_candidates": 0,
    "global_candidates": 0
  }}
}}
"""

        try:
            result = await self.generate_json(
                synthesis_prompt, temperature=0.03
            )

            # Final server-side verification: AI-selected competitors must also
            # exist in the deterministic evidence candidate sets.
            deterministic_local = {
                str(x.get("name", "")).strip().lower(): x
                for x in fallback.get("local_competitors", [])
                if isinstance(x, dict)
            }
            deterministic_global = {
                str(x.get("name", "")).strip().lower(): x
                for x in fallback.get("market_leaders", [])
                if isinstance(x, dict)
            }

            verified_local = []
            for x in result.get("local_competitors", []):
                if not isinstance(x, dict):
                    continue
                key = str(x.get("name", "")).strip().lower()
                if key in deterministic_local:
                    base = deterministic_local[key]
                    verified_local.append({
                        **base,
                        **x,
                        "sources": list(dict.fromkeys(
                            (base.get("sources") or []) + (x.get("sources") or [])
                        ))[:5],
                    })

            verified_global = []
            for x in result.get("market_leaders", []):
                if not isinstance(x, dict):
                    continue
                key = str(x.get("name", "")).strip().lower()
                if key in deterministic_global:
                    base = deterministic_global[key]
                    verified_global.append({
                        **base,
                        **x,
                        "sources": list(dict.fromkeys(
                            (base.get("sources") or []) + (x.get("sources") or [])
                        ))[:5],
                    })

            result["local_competitors"] = verified_local[:5]
            result["market_leaders"] = verified_global[:5]
            result["target"] = {
                **fallback.get("target", {}),
                **(result.get("target") or {}),
            }
            result["research_coverage"] = {
                **fallback.get("research_coverage", {}),
                **(result.get("research_coverage") or {}),
                "status": "live_ddgs",
                "provider": "DDGS",
                "target_results": len(target_raw.split("SEARCH QUERY:")) - 1,
                "local_results": len(local_raw.split("SEARCH QUERY:")) - 1,
                "global_results": len(global_raw.split("SEARCH QUERY:")) - 1,
                "local_candidates": len(result["local_competitors"]),
                "global_candidates": len(result["market_leaders"]),
            }
            return result

        except HTTPException as exc:
            if exc.status_code == 429:
                fallback["insight_summary"] = (
                    "Live DDGS research completed, but the live AI synthesis model is "
                    "temporarily rate-limited. The competitors below are evidence-filtered "
                    "live-search candidates only; no AI conclusions were generated."
                )
                fallback["research_coverage"]["ai_synthesis"] = "rate_limited"
                return fallback
            raise

try:
    engine = GrowthPilotEngine()
    print(f"[STARTUP] GrowthPilot using model: {engine.model}")
except Exception as exc:
    print(f"[STARTUP ERROR] {type(exc).__name__}: {exc}")
    engine = None


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "GrowthPilot AI",
        "model": engine.model if engine else "not configured",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy" if engine else "error",
        "model": engine.model if engine else None,
        "groq_configured": engine is not None,
        "ddgs_configured": True,
    }


@app.post("/api/growth-analysis")
async def handle_growth_analysis(payload: AnalysisRequest):
    if engine is None:
        raise HTTPException(
            status_code=500,
            detail="GrowthPilot backend is not configured. Check GROQ_API_KEY.",
        )

    try:
        return await engine.run_full_analysis(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location,
            goal=payload.goal,
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[GROWTH ENDPOINT ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Growth analysis failed: {exc}",
        )


@app.post("/api/visibility-audit")
async def handle_visibility_audit(payload: AnalysisRequest):
    if engine is None:
        raise HTTPException(
            status_code=500,
            detail="GrowthPilot backend is not configured. Check GROQ_API_KEY.",
        )

    try:
        return await engine.run_visibility_audit(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location,
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[VISIBILITY ENDPOINT ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Visibility audit failed: {exc}",
        )
