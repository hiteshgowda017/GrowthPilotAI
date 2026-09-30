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
                max_completion_tokens=8000,
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
            print(f"[GROQ ERROR] {type(exc).__name__}: {exc}")
            raise HTTPException(
                status_code=502,
                detail=f"Groq AI request failed: {exc}",
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
        """Production visibility audit using browser search + DDGS fallback."""
        print(f"=== VISIBILITY AUDIT: {name.upper()} ===")

        research_prompt = f"""
You are conducting a real-time competitive intelligence audit for GrowthPilot.

TARGET BUSINESS
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

SEARCH THE LIVE WEB and build three evidence sets.

A) TARGET BUSINESS
Find and verify:
- official website and public company profiles
- current services/products
- location/presence
- search discoverability
- reviews/public customer signals
- LinkedIn, Instagram, Facebook and other public profiles
- recent public mentions/news

B) LOCAL COMPETITORS
Find real businesses competing in or near {location}.
Do NOT only return famous brands.
Actively seek small, independent, niche, newer and poorly recognized businesses.
Search local results, Justdial, Sulekha, IndiaMART, social networks, local
publications and company websites.

For each candidate verify that:
1. it appears to be a real business,
2. it is relevant to {industry}, and
3. it is geographically relevant to {location}.
A directory listing alone does not prove quality or market position.

C) GLOBAL LEADERS
Find genuinely international companies relevant to {industry}.
Prefer official sources, reputable business/industry publications and market
sources. Do not return a famous company merely because it is famous.

For every named company provide supporting evidence and a URL/source when available.
Do not guess. Organize findings under TARGET EVIDENCE, LOCAL COMPETITORS, GLOBAL LEADERS.
"""

        # One browser session is used to reduce latency and provider rate limits.
        browser_data = await self.browser_research(research_prompt)

        # DDGS remains the secondary LIVE search layer.
        ddgs_data = ""
        if not browser_data:
            print("[VISIBILITY] Browser research unavailable; using DDGS fallback.")
            fallback_queries = [
                f'"{name}" "{location}" {industry} official reviews social media',
                f'"{industry}" businesses "{location}" local competitors',
                f'site:justdial.com "{industry}" "{location}"',
                f'site:sulekha.com "{industry}" "{location}"',
                f'top global "{industry}" companies',
                f'leading international "{industry}" companies',
            ]

            chunks = []
            for query in fallback_queries:
                region = "us-en" if ("global" in query or "international" in query) else "in-en"
                result = await self.robust_search(
                    query,
                    max_results=5,
                    retries=2,
                    region=region,
                )
                if result:
                    chunks.append(result)

            ddgs_data = "\n\n".join(chunks)

        live_data = (browser_data or ddgs_data).strip()

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
                    "No live search evidence was returned by the configured "
                    "research providers. Scores were not generated."
                ),
                "research_coverage": {
                    "status": "no_live_evidence",
                    "browser_search": "attempted",
                    "ddgs_fallback": "attempted",
                },
            }

        synthesis_prompt = f"""
You are GrowthPilot senior competitive-intelligence analyst.

Everything below is LIVE WEB RESEARCH. Use ONLY this evidence.
Do not use general or pretrained knowledge to fill gaps.

TARGET
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

LIVE RESEARCH EVIDENCE
======================
{live_data[:50000]}

RULES
1. Never invent a company, location, service, review, score or ranking.
2. Local competitors must be genuinely relevant to {location}.
3. Prefer smaller/independent local businesses when the evidence supports them.
4. Global leaders must be genuinely international and relevant to {industry}.
5. Directory listings identify candidates but do not prove quality or leadership.
6. Score DIGITAL VISIBILITY only, not revenue, business quality or size.
7. Scores are estimates from observable online signals.
8. Give each company an evidence level: High, Medium or Low.
9. If evidence is insufficient, omit the company rather than guessing.
10. Recommendations must follow from evidence in the supplied research.
11. Do not use generic industry knowledge as observed research.
12. Return ONLY valid JSON.

RETURN EXACTLY
===============
{{
  "target": {{
    "name": "{name}",
    "score": 0,
    "evidence_level": "High, Medium, Low, or None",
    "evidence_summary": "Concrete evidence found for the target"
  }},
  "local_competitors": [],
  "market_leaders": [],
  "insight_summary": "Evidence-based comparison of the target against the discovered set.",
  "research_coverage": {{
    "status": "live_evidence",
    "provider": "Groq Browser Search or DDGS fallback",
    "target": "researched",
    "local": "researched",
    "global": "researched"
  }}
}}

Populate the two arrays with up to 5 verified companies each when supported.
Each company object must have: name, score, evidence_level, evidence_summary.
Never fill an empty slot with a guess.
"""
        print("[VISIBILITY] Synthesizing live evidence...")
        return await self.generate_json(synthesis_prompt, temperature=0.1)


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
