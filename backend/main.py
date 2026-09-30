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
        max_results: int = 5,
        retries: int = 2,
    ) -> str:
        """Run live DDGS search without blocking the FastAPI event loop."""
        for attempt in range(1, retries + 1):
            try:
                print(f"[SEARCH] {query}")

                def do_search():
                    # Use the installed ddgs package.
                    with DDGS() as search:
                        return list(
                            search.text(
                                query,
                                max_results=max_results,
                            )
                        )

                results = await asyncio.to_thread(do_search)

                if results:
                    formatted = []
                    for result in results:
                        formatted.append(
                            f"- {result.get('title', '')}\n"
                            f"  {result.get('body', '')}\n"
                            f"  Source: {result.get('href', '')}"
                        )
                    return "\n".join(formatted)

                print(f"[SEARCH WARNING] No results for: {query}")

            except Exception as exc:
                print(
                    f"[SEARCH WARNING] Attempt {attempt}/{retries} failed: "
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
        print(f"=== VISIBILITY AUDIT: {name.upper()} ===")

        local_search, target_search, market_search = await asyncio.gather(
            self.robust_search(
                f'independent {industry} businesses in {location}'
            ),
            self.robust_search(
                f'"{name}" {location} website reviews social media'
            ),
            self.robust_search(
                f'leading companies in {industry} industry'
            ),
        )

        prompt = f"""
You are a Senior SEO and Digital Visibility Analyst.

TARGET BUSINESS
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

SEARCH DATA

TARGET:
{target_search[:8000]}

LOCAL BUSINESSES:
{local_search[:8000]}

MARKET LEADERS:
{market_search[:8000]}

RULES
1. Use only supplied search evidence.
2. Do not invent companies.
3. Identify up to 5 real local competitors and up to 5 relevant market leaders.
4. Scores are evidence-based estimates from 0 to 100.
5. Return ONLY valid JSON.

Return:
{{
  "target": {{"name": "{name}", "score": 0}},
  "local_competitors": [{{"name": "Competitor", "score": 0}}],
  "market_leaders": [{{"name": "Market Leader", "score": 0}}],
  "insight_summary": "Two sentence evidence-based summary."
}}
"""

        return await self.generate_json(prompt, temperature=0.3)


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
