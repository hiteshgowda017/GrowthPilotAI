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

    async def robust_search(
        self,
        query: str,
        max_results: int = 8,
        retries: int = 2,
        region: str = "in-en",
    ) -> str:
        """Run resilient live DDGS metasearch with regional and engine fallbacks."""
        for attempt in range(1, retries + 1):
            for backend in ("auto", "google,brave,bing,duckduckgo"):
                try:
                    print(
                        f"[SEARCH] region={region} backend={backend} query={query}"
                    )

                    def do_search():
                        with DDGS() as search:
                            return list(
                                search.text(
                                    query,
                                    region=region,
                                    safesearch="moderate",
                                    max_results=max_results,
                                    backend=backend,
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
                        f"[SEARCH WARNING] {backend} failed for '{query}': "
                        f"{type(exc).__name__}: {exc}"
                    )

            if attempt < retries:
                await asyncio.sleep(1)

        return "No verified external search data was available."

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
        """
        Deep live visibility research across:
        - exact target business
        - very local/small competitors
        - global market leaders
        """
        print(f"=== DEEP VISIBILITY AUDIT: {name.upper()} ===")

        target_queries = [
            f'"{name}" "{location}"',
            f'"{name}" {location} reviews',
            f'"{name}" {location} services',
            f'"{name}" {location} contact',
            f'"{name}" {location} Facebook Instagram LinkedIn',
        ]

        local_queries = [
            f'"{industry}" "{location}" companies businesses',
            f'"{industry}" businesses near "{location}"',
            f'top "{industry}" businesses "{location}"',
            f'site:justdial.com "{industry}" "{location}"',
            f'site:sulekha.com "{industry}" "{location}"',
            f'site:indiamart.com "{industry}" "{location}"',
            f'site:facebook.com "{industry}" "{location}"',
            f'site:instagram.com "{industry}" "{location}"',
        ]

        global_queries = [
            f'top global "{industry}" companies',
            f'leading global "{industry}" companies',
            f'largest "{industry}" companies worldwide',
            f'global "{industry}" market leaders',
            f'best known international "{industry}" companies',
            f'global "{industry}" companies official websites',
        ]

        async def collect(queries: list[str], region: str, limit: int) -> str:
            results = await asyncio.gather(
                *(
                    self.robust_search(
                        query,
                        max_results=7,
                        retries=2,
                        region=region,
                    )
                    for query in queries
                )
            )
            usable = [
                result for result in results
                if result and "No verified external search data" not in result
            ]
            return "\n\n".join(usable)[:limit]

        target_data, local_data, global_data = await asyncio.gather(
            collect(target_queries, "in-en", 18000),
            collect(local_queries, "in-en", 28000),
            collect(global_queries, "us-en", 24000),
        )

        prompt = f"""
You are GrowthPilot AI's Deep Digital Visibility Research Engine.

Research the target business at THREE levels:
1. Exact target business.
2. Very local businesses, including small, poorly recognized businesses.
3. Global market leaders in the same industry.

TARGET
======
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

TARGET LIVE SEARCH EVIDENCE
===========================
{target_data}

LOCAL MARKET LIVE SEARCH EVIDENCE
==================================
{local_data}

GLOBAL MARKET LIVE SEARCH EVIDENCE
===================================
{global_data}

RESEARCH RULES
==============
1. Use ONLY the supplied live search evidence.
2. NEVER invent a company, competitor, leader, score, review or fact.
3. Directory sources such as Justdial, Sulekha and IndiaMART can be used
   to DISCOVER small local businesses. They are evidence sources, not
   automatically competitors.
4. Do not require a local company to be famous or nationally recognized.
5. If a small company is identifiable but has limited online evidence,
   keep it and mark its evidence level LOW instead of dropping it.
6. Local competitors must be geographically relevant to {location}.
7. Global leaders must be genuinely international/relevant to {industry}.
8. Keep local competitors and global leaders in separate lists.
9. Scores are evidence-based ESTIMATES from 0 to 100, not audited market share.
10. If evidence is insufficient, say so instead of filling the list with guesses.
11. Return ONLY valid JSON.

OUTPUT
======
{{
  "target": {{
    "name": "{name}",
    "score": 0,
    "evidence_level": "High, Medium, Low, or None"
  }},
  "local_competitors": [
    {{
      "name": "Real local business",
      "score": 0,
      "evidence": "Short evidence-based explanation",
      "evidence_level": "High, Medium, or Low"
    }}
  ],
  "market_leaders": [
    {{
      "name": "Real global market leader",
      "score": 0,
      "evidence": "Short evidence-based explanation",
      "evidence_level": "High, Medium, or Low"
    }}
  ],
  "insight_summary": "Two or three sentences explaining local and global visibility.",
  "research_coverage": {{
    "target_queries_run": {len(target_queries)},
    "local_queries_run": {len(local_queries)},
    "global_queries_run": {len(global_queries)},
    "local_research": "Live multi-query regional search",
    "global_research": "Live multi-query global search"
  }}
}}

Aim for up to 5 local competitors and up to 5 global leaders, but NEVER
invent names just to fill slots.
"""
        print("[VISIBILITY] Sending deep local + global evidence to Groq...")
        return await self.generate_json(prompt, temperature=0.2)


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
