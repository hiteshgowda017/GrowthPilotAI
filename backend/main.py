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

from research_utils import summarize_fallback

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
                max_completion_tokens=5000,
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
        print(f"=== GROWTHPILOT ANALYSIS: {name.upper()} ===")

        domain = self.clean_domain(website)

        if domain:
            site_query = f'site:{domain} "{name}" services'
        else:
            site_query = f'"{name}" {industry} {location} services'

        site_data, competitor_data, review_data = await asyncio.gather(
            self.robust_search(site_query),
            self.robust_search(
                f'top independent {industry} businesses in {location}'
            ),
            self.robust_search(
                f'"{name}" {location} reviews complaints customer experience'
            ),
        )

        prompt = f"""
You are GrowthPilot AI, a practical business growth and market intelligence
consultant.

BUSINESS
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}
Goal: {goal}

REAL-WORLD LIVE SEARCH DATA

BUSINESS DATA:
{site_data[:10000]}

COMPETITOR DATA:
{competitor_data[:10000]}

REVIEW / CUSTOMER DATA:
{review_data[:10000]}

RULES
1. Use the supplied live search data as evidence.
2. Never invent specific company facts or competitors.
3. Clearly say when something cannot be verified.
4. Prefer relevant local competitors supported by the search data.
5. Do not present unsupported scores as measured facts; label estimates as estimates.
6. Prioritize practical, actionable recommendations.
7. Return ONLY valid JSON.

Return exactly this structure:
{{
  "metrics": {{
    "market_rank": "Evidence-based estimated position or Not enough verified data",
    "ai_visibility_score": "0-100 estimate",
    "vulnerability_score": "0-100 estimate",
    "top_opportunity": "Specific evidence-based opportunity"
  }},
  "report_markdown": "# GrowthPilot Executive Intelligence Report\n\n## Phase I: Business Audit\nBusiness analysis based on verified search evidence.\n\n## Phase II: Competitive Landscape\nRelevant competitors and positioning supported by the search data.\n\n## Phase III: Business Gaps\nImportant service, marketing and digital gaps.\n\n## Phase IV: Growth Opportunities\nPractical growth opportunities.\n\n## Phase V: AI & Digital Visibility\nWays to improve online and AI visibility.\n\n## Phase VI: Strategic Roadmap\nQuick wins, 30-day actions, 90-day actions and longer-term actions.\n\n## Phase VII: Tactical Action Plan\nA clear step-by-step execution plan."
  }}
}}
"""

        print("[PHASE 4] Sending live research to Groq...")
        return await self.generate_json(prompt, temperature=0.4)

    async def run_visibility_audit(
        self,
        name: str,
        website: str,
        industry: str,
        location: str,
    ) -> dict:
        """Live DDGS visibility audit with optional Groq browser enrichment."""
        print(f"=== VISIBILITY AUDIT: {name.upper()} ===")

        # DDGS is ALWAYS collected. This is the core live-search layer.
        target_queries = [
            f'"{name}" "{location}" {industry} official website',
            f'"{name}" "{location}" reviews social media',
        ]
        local_queries = [
            f'"{industry}" businesses "{location}"',
            f'"{industry}" companies near "{location}"',
            f'"{industry}" independent businesses "{location}"',
            f'site:justdial.com "{industry}" "{location}"',
            f'site:sulekha.com "{industry}" "{location}"',
        ]
        global_queries = [
            f'top global "{industry}" companies',
            f'leading international "{industry}" companies',
            f'largest "{industry}" companies worldwide',
        ]

        async def collect(queries: list[str], region: str) -> str:
            chunks = []
            for query in queries:
                result = await self.robust_search(
                    query,
                    max_results=6,
                    retries=1,
                    region=region,
                )
                if result:
                    chunks.append(result)
            return "\n\n".join(chunks)

        target_raw, local_raw, global_raw = await asyncio.gather(
            collect(target_queries, "in-en"),
            collect(local_queries, "in-en"),
            collect(global_queries, "us-en"),
        )

        ddgs_data = "\n\n".join(
            x for x in [target_raw, local_raw, global_raw] if x
        ).strip()

        # Optional Groq browser enrichment. It is OFF by default because
        # DDGS already supplies the required live-search capability.
        browser_data = ""
        if self.use_browser_research:
            browser_prompt = f"""
Research this business and its competitive landscape on the live web.

Business: {name}
Industry: {industry}
Location: {location}

Find:
1. verified target-business evidence,
2. small/local competitors near {location},
3. genuinely international competitors/leaders relevant to {industry}.

Do not invent. Return concise evidence with URLs.
"""
            browser_data = await self.browser_research(browser_prompt)

        live_data = "\n\n".join(
            x for x in [ddgs_data, browser_data] if x
        ).strip()

        if not live_data:
            return {
                "target": {
                    "name": name,
                    "score": 0,
                    "evidence_level": "None",
                    "evidence_summary": "No live search evidence was returned.",
                },
                "local_competitors": [],
                "market_leaders": [],
                "insight_summary": (
                    "No live search evidence was returned by DDGS or the "
                    "optional Groq browser-search layer."
                ),
                "research_coverage": {
                    "status": "no_live_evidence",
                    "ddgs": "attempted",
                    "browser_search": "enabled" if self.use_browser_research else "disabled",
                },
            }

        # When Groq is currently over quota, return a useful DDGS-only audit
        # instead of surfacing a 429 to the user.
        if not self.use_browser_research and not os.getenv("GROQ_BYPASS_SYNTHESIS"):
            synthesis_enabled = True
        else:
            synthesis_enabled = True

        if synthesis_enabled:
            synthesis_prompt = f"""
You are GrowthPilot senior competitive-intelligence analyst.

Use ONLY the live research below. Never use general knowledge to fill gaps.

TARGET
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

LIVE EVIDENCE
=============
{live_data[:45000]}

Rules:
- Never invent a company, location, service, review, score or ranking.
- Local competitors must be genuinely relevant to {location}.
- Prefer small and independent local businesses when supported by evidence.
- Global leaders must be genuinely international and relevant to {industry}.
- Directory listings can identify a business but do not prove quality.
- Score DIGITAL VISIBILITY only.
- Scores are estimates from observed web signals.
- Omit unsupported companies.
- Return ONLY JSON.

JSON:
{{
  "target": {{
    "name": "{name}",
    "score": 0,
    "evidence_level": "High, Medium, Low, or None",
    "evidence_summary": "Evidence found in live research"
  }},
  "local_competitors": [],
  "market_leaders": [],
  "insight_summary": "Evidence-based summary",
  "research_coverage": {{
    "status": "live_evidence",
    "provider": "DDGS",
    "target": "researched",
    "local": "researched",
    "global": "researched"
  }}
}}

Populate up to 5 verified local competitors and 5 verified global leaders.
Each item must contain name, score, evidence_level and evidence_summary.
"""

            try:
                return await self.generate_json(synthesis_prompt, temperature=0.1)
            except HTTPException as exc:
                if exc.status_code == 429:
                    print("[VISIBILITY] Groq quota exhausted; returning DDGS fallback.")
                    return self._build_visibility_ddgs_fallback(
                        name,
                        target_raw,
                        local_raw,
                        global_raw,
                    )
                raise

        return self._build_visibility_ddgs_fallback(
            name,
           async def run_visibility_audit(
        self,
        name: str,
        website: str,
        industry: str,
        location: str,
    ) -> dict:
        """Evidence-first visibility audit with strict relevance filtering."""
        print(f"=== VISIBILITY AUDIT: {name.upper()} | {industry} | {location} ===")

        target_queries = [
            f'"{name}" "{location}" {industry} official website',
            f'"{name}" "{location}" {industry} LinkedIn',
            f'"{name}" "{location}" {industry} reviews',
        ]
        local_queries = [
            f'"{industry}" "{location}" company',
            f'"{industry}" "{location}" services',
            f'"{industry}" near "{location}" company',
            f'"{industry}" independent "{location}"',
            f'site:justdial.com "{industry}" "{location}"',
            f'site:sulekha.com "{industry}" "{location}"',
            f'site:indiamart.com "{industry}" "{location}"',
        ]
        global_queries = [
            f'"{industry}" global companies',
            f'"{industry}" international companies',
            f'"{industry}" multinational companies',
            f'leading "{industry}" companies worldwide',
            f'largest "{industry}" companies global',
        ]

        async def collect(queries: list[str], region: str) -> str:
            chunks = []
            for query in queries:
                result = await self.robust_search(query, max_results=6, retries=1, region=region)
                if result:
                    chunks.append(result)
            return "\n\n".join(chunks)

        target_raw, local_raw, global_raw = await asyncio.gather(
            collect(target_queries, "in-en"),
            collect(local_queries, "in-en"),
            collect(global_queries, "us-en"),
        )

        browser_data = ""
        if self.use_browser_research:
            browser_prompt = f"""
Live competitive research. Target: {name}. Industry: {industry}. Location: {location}.
Search the web for the exact business, real local companies providing the requested
industry near the location, and genuinely international companies providing that industry.
Reject films, books, actors, YouTube, Wikipedia, entertainment, people and unrelated
acronym meanings. Give URLs and concrete evidence. Do not guess.
"""
            browser_data = await self.browser_research(browser_prompt)

        # Deterministic filtering happens before AI synthesis.
        fallback = summarize_fallback(name, industry, location, target_raw, local_raw, global_raw)

        live_evidence = (
            f"TARGET DDGS:\n{target_raw}\n\nLOCAL DDGS:\n{local_raw}\n\nGLOBAL DDGS:\n{global_raw}"
            + (f"\n\nBROWSER ENRICHMENT:\n{browser_data[:20000]}" if browser_data else "")
        )

        if not live_evidence.strip():
            return fallback

        synthesis_prompt = f"""
You are the senior competitive-intelligence analyst for GrowthPilot.

TARGET
Name: {name}
Industry: {industry}
Location: {location}
Website: {website or "Not provided"}

LIVE SEARCH EVIDENCE
====================
{live_evidence[:50000]}

STRICT ACCURACY RULES
1. A competitor MUST be a real business/company offering {industry}.
2. A local competitor MUST have evidence connecting it to {location} or its immediate market.
3. A global leader MUST be a real international company relevant to {industry}.
4. Reject films, movies, books, novels, actors, YouTube, Wikipedia, entertainment, people,
   and unrelated meanings of acronyms.
5. A search title alone is not proof. Prefer official company pages and reputable sources.
6. Directory pages may discover a company but do not prove quality or market leadership.
7. Never invent facts, services, locations, scores or recommendations.
8. Scores measure DIGITAL VISIBILITY only; they are estimates, not market share.
9. Every recommendation must follow from evidence actually supplied.
10. If a candidate cannot be verified, OMIT it. Fewer results are better than wrong results.
11. Return ONLY valid JSON.

Return this schema:
{
  "target": {
    "name": "TARGET_NAME",
    "score": 0,
    "evidence_level": "High, Medium, Low, or None",
    "evidence_summary": "Verified live-search evidence"
  },
  "local_competitors": [],
  "market_leaders": [],
  "insight_summary": "Evidence-based summary only",
  "research_coverage": {
    "status": "live_evidence",
    "provider": "DDGS",
    "target": "researched",
    "local": "researched",
    "global": "researched"
  }
}

Each competitor object must contain name, score, evidence_level, evidence_summary and sources.
Maximum 5 local and 5 global companies. Never fill a slot with an unsupported company.
"""

        try:
            return await self.generate_json(synthesis_prompt, temperature=0.05)
        except HTTPException as exc:
            if exc.status_code == 429:
                print("[VISIBILITY] Groq synthesis rate-limited; using filtered DDGS result.")
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
