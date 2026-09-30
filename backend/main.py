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

        return "No verified external search data was available."

    async def browser_research(self, prompt: str) -> str:
        """Use Groq's built-in browser search for real-time research."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a web research agent. Search the live web. "
                            "Use multiple relevant sources. Do not guess. "
                            "Return concise evidence with company names, locations "
                            "and source references when available."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                reasoning_effort="low",
                include_reasoning=False,
                tool_choice="required",
                tools=[{"type": "browser_search"}],
                max_completion_tokens=5000,
            )
            content = response.choices[0].message.content
            if content:
                return content
        except Exception as exc:
            print(f"[BROWSER SEARCH WARNING] {type(exc).__name__}: {exc}")

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
        print(f"=== PRODUCTION VISIBILITY AUDIT: {name.upper()} ===")

        target_prompt = f"""
Research this exact business on the LIVE WEB.

Business: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

Find the official website/profiles, current services, local presence,
search footprint, reviews/public customer signals, social profiles and
recent mentions. Prefer primary and current sources. Return concrete
evidence and source references. Do not guess.
"""

        local_prompt = f"""
Perform DEEP LOCAL COMPETITOR DISCOVERY on the LIVE WEB.

Industry: {industry}
Location: {location}

Find real businesses competing locally. Do not only return famous companies.
Search local business websites, local results, Justdial, Sulekha, IndiaMART,
Facebook, Instagram, LinkedIn, local directories and publications.

Look specifically for small, newly established, niche, independent or poorly
recognized businesses in or near {location}. For every candidate, verify that
it is a real business and explain why it is locally relevant. Return evidence
and source references. Do not invent names.
"""

        global_prompt = f"""
Perform GLOBAL MARKET LEADER DISCOVERY on the LIVE WEB.

Industry: {industry}

Find real international companies that are relevant leaders or major
competitors in this industry. Prefer official company sites, reputable
business sources, industry publications and market reports.

Do not return random famous companies. Each company must be genuinely
relevant to {industry}. Return evidence and source references. Do not invent.
"""

        # Sequential research reduces provider rate limiting.
        target_browser = await self.browser_research(target_prompt)
        local_browser = await self.browser_research(local_prompt)
        global_browser = await self.browser_research(global_prompt)

        # DDGS remains the secondary live-search layer.
        if not target_browser:
            target_browser = await self.robust_search(
                f'"{name}" "{location}" reviews services website social media',
                max_results=8,
                retries=2,
                region="in-en",
            )
        if not local_browser:
            local_browser = await self.robust_search(
                f'"{industry}" businesses "{location}" local competitors',
                max_results=8,
                retries=2,
                region="in-en",
            )
        if not global_browser:
            global_browser = await self.robust_search(
                f'global leading "{industry}" companies market leaders',
                max_results=8,
                retries=2,
                region="us-en",
            )

        target_data = target_browser[:18000]
        local_data = local_browser[:24000]
        global_data = global_browser[:20000]

        if not (target_data.strip() or local_data.strip() or global_data.strip()):
            return {
                "target": {
                    "name": name,
                    "score": 0,
                    "evidence_level": "None",
                    "evidence_summary": "No live evidence was returned.",
                },
                "local_competitors": [],
                "market_leaders": [],
                "insight_summary": (
                    "The live research providers returned no usable evidence. "
                    "No competitor or visibility score was generated."
                ),
                "research_coverage": {
                    "status": "no_live_evidence",
                    "browser_search": True,
                    "ddgs_fallback": True,
                },
            }

        prompt = f"""
You are GrowthPilot AI's senior competitive intelligence analyst.

This is an EVIDENCE-ONLY report. The supplied material comes from LIVE WEB
RESEARCH. Do not use pretrained/general knowledge to fill missing facts.

TARGET
Name: {name}
Website: {website or "Not provided"}
Industry: {industry}
Location: {location}

TARGET LIVE RESEARCH
{target_data}

LOCAL LIVE RESEARCH
{local_data}

GLOBAL LIVE RESEARCH
{global_data}

STRICT RULES
1. Use only information supported by the supplied live research.
2. NEVER invent a company, competitor, review, score, location or fact.
3. A directory listing may identify a local company, but does not prove
   services, quality or market position unless supported by evidence.
4. Prefer small local companies when evidence shows they exist and are relevant.
5. Keep local competitors geographically relevant to {location}.
6. Global leaders must be genuinely international and relevant to {industry}.
7. Score DIGITAL VISIBILITY, not company size or business quality.
8. Scores are estimates from observable evidence, not audited market share.
9. If evidence is weak, use a low evidence level rather than guessing.
10. If evidence does not support a recommendation, do not make it.
11. Never use generic industry knowledge as if it were live evidence.
12. Return ONLY valid JSON.

OUTPUT
Return exactly:
{{
  "target": {{
    "name": "{name}",
    "score": 0,
    "evidence_level": "High, Medium, Low, or None",
    "evidence_summary": "What was actually found"
  }},
  "local_competitors": [
    {{
      "name": "Real local company",
      "score": 0,
      "evidence_level": "High, Medium, or Low",
      "evidence_summary": "Why it is relevant based on live evidence"
    }}
  ],
  "market_leaders": [
    {{
      "name": "Real global company",
      "score": 0,
      "evidence_level": "High, Medium, or Low",
      "evidence_summary": "Why it is relevant based on live evidence"
    }}
  ],
  "insight_summary": "Evidence-based summary only.",
  "research_coverage": {{
    "target": "Live browser/DDGS research",
    "local": "Live browser/DDGS research",
    "global": "Live browser/DDGS research"
  }}
}}

Return up to 5 local competitors and up to 5 global leaders when supported.
Never fill a missing slot with a guess.
"""
        print("[VISIBILITY] Synthesizing evidence-only audit...")
        return await self.generate_json(prompt, temperature=0.1)


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
