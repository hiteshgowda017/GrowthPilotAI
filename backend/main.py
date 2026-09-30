import os
import json
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import AsyncGroq
from dotenv import load_dotenv

# Current DDGS package
from ddgs import DDGS

load_dotenv()

app = FastAPI(title="GrowthPilot AI API")


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# REQUEST MODEL
# ==========================================================

class AnalysisRequest(BaseModel):
    business_name: str
    website: str
    industry: str
    location: str
    goal: str


# ==========================================================
# GROWTH PILOT ENGINE
# ==========================================================

class GrowthPilotEngine:

    def __init__(self):

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to your deployment environment variables."
            )

        self.client = AsyncGroq(api_key=api_key)

        # Current Groq model
        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-20b"
        )

    # ======================================================
    # WEB SEARCH
    # ======================================================

    async def robust_search(
        self,
        query: str,
        max_results: int = 5,
        retries: int = 2
    ) -> str:

        """
        Performs web search without allowing search failure
        to crash the complete GrowthPilot analysis.
        """

        for attempt in range(retries):

            try:

                print(f"[SEARCH] {query}")

                def do_search():
                    results = DDGS().text(
                        query,
                        max_results=max_results
                    )
                    return results

                results = await asyncio.to_thread(do_search)

                if results:

                    formatted = []

                    for result in results:

                        title = result.get("title", "")
                        body = result.get("body", "")
                        href = result.get("href", "")

                        formatted.append(
                            f"- {title}\n"
                            f"  {body}\n"
                            f"  Source: {href}"
                        )

                    return "\n".join(formatted)

            except Exception as e:

                print(
                    f"[SEARCH WARNING] Attempt "
                    f"{attempt + 1}/{retries}: {str(e)}"
                )

                await asyncio.sleep(1)

        # IMPORTANT:
        # Search failure should NOT stop the AI analysis.

        print("[SEARCH WARNING] Search unavailable.")

        return "No external search data was available."


    # ======================================================
    # GROQ JSON CALL
    # ======================================================

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.4
    ) -> dict:

        try:

            response = await self.client.chat.completions.create(

                model=self.model,

                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                # GPT-OSS reasoning configuration
                reasoning_effort="low",
                include_reasoning=False,

                # JSON output
                response_format={
                    "type": "json_object"
                },

                temperature=temperature,

                # Prevent unnecessarily huge responses
                max_completion_tokens=8000
            )

            content = response.choices[0].message.content

            if not content:
                raise ValueError("Groq returned an empty response.")

            return json.loads(content)

        except json.JSONDecodeError as e:

            print(
                f"[JSON ERROR] Model returned invalid JSON: {str(e)}"
            )

            raise HTTPException(
                status_code=500,
                detail="AI returned an invalid JSON response."
            )

        except Exception as e:

            print(
                f"[GROQ ERROR] {type(e).__name__}: {str(e)}"
            )

            raise HTTPException(
                status_code=500,
                detail=f"Groq AI request failed: {str(e)}"
            )


    # ======================================================
    # ENGINE 1
    # FULL GROWTH ANALYSIS
    # ======================================================

    async def run_full_analysis(
        self,
        name: str,
        website: str,
        industry: str,
        location: str,
        goal: str
    ) -> dict:

        print(
            f"\n=== GROWTHPILOT ANALYSIS: "
            f"{name.upper()} ==="
        )

        clean_url = (
            website
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )

        # --------------------------------------------------
        # WEB RESEARCH
        # --------------------------------------------------

        print("[PHASE 1] Searching business information...")

        site_data = await self.robust_search(
            f'site:{clean_url} "{name}" services'
        )

        print("[PHASE 2] Searching competitors...")

        competitor_data = await self.robust_search(
            f'top independent {industry} businesses in {location}'
        )

        print("[PHASE 3] Searching reviews and customer problems...")

        review_data = await self.robust_search(
            f'"{name}" {location} reviews complaints customer experience'
        )

        # --------------------------------------------------
        # LIMIT SEARCH DATA
        # Prevent massive prompts
        # --------------------------------------------------

        site_data = site_data[:10000]
        competitor_data = competitor_data[:10000]
        review_data = review_data[:10000]

        # --------------------------------------------------
        # AI PROMPT
        # --------------------------------------------------

        prompt = f"""
You are GrowthPilot AI, a practical business growth
and market intelligence consultant.

Analyze the following business.

BUSINESS
Name: {name}
Website: {website}
Industry: {industry}
Location: {location}
Goal: {goal}

REAL-WORLD SEARCH DATA
=====================

BUSINESS DATA:
{site_data}

COMPETITOR DATA:
{competitor_data}

REVIEW / CUSTOMER DATA:
{review_data}


IMPORTANT RULES
===============

1. Use the provided search data as evidence.

2. Do not invent specific facts about the company.

3. If information is unavailable, clearly state that
   the information could not be verified.

4. Identify real local competitors only when supported
   by the supplied search data.

5. Do not use global corporations as local competitors.

6. Scores must be based on the available evidence.

7. Keep the report detailed but concise.

8. Prioritize actionable business recommendations.

9. Do not repeat the same information in multiple sections.

10. Return ONLY valid JSON.

OUTPUT FORMAT
=============

{{
    "metrics": {{
        "market_rank": "Rank or estimated position based on available evidence",
        "ai_visibility_score": "0-100",
        "vulnerability_score": "0-100",
        "top_opportunity": "Specific opportunity"
    }},

    "report_markdown": "# GrowthPilot Executive Intelligence Report\\n\\n## Phase I: Business Audit\\nDetailed analysis of the business based on available evidence.\\n\\n## Phase II: Competitive Landscape\\nIdentify relevant local competitors and explain their positioning.\\n\\n## Phase III: Business Gaps\\nExplain important service, marketing, digital and operational gaps.\\n\\n## Phase IV: Growth Opportunities\\nIdentify practical opportunities for growth.\\n\\n## Phase V: AI & Digital Visibility\\nExplain how the business can improve its online and AI visibility.\\n\\n## Phase VI: Strategic Roadmap\\nProvide actionable quick wins, 30-day actions, 90-day actions and longer-term recommendations.\\n\\n## Phase VII: Tactical Action Plan\\nProvide a clear step-by-step execution plan."
    }}
}}

Remember:

Return ONLY JSON.
No markdown code block around the JSON.
"""


        print("[PHASE 4] Sending analysis to Groq...")

        return await self.generate_json(
            prompt,
            temperature=0.4
        )


    # ======================================================
    # ENGINE 2
    # VISIBILITY AUDIT
    # ======================================================

    async def run_visibility_audit(
        self,
        name: str,
        website: str,
        industry: str,
        location: str
    ) -> dict:

        print(
            f"\n=== VISIBILITY AUDIT: "
            f"{name.upper()} ==="
        )

        # --------------------------------------------------
        # SEARCH
        # --------------------------------------------------

        local_search = await self.robust_search(
            f'independent {industry} businesses in {location}'
        )

        target_search = await self.robust_search(
            f'"{name}" {location} website reviews social media'
        )

        market_search = await self.robust_search(
            f'leading companies in {industry} industry'
        )

        local_search = local_search[:8000]
        target_search = target_search[:8000]
        market_search = market_search[:8000]

        # --------------------------------------------------
        # PROMPT
        # --------------------------------------------------

        prompt = f"""
You are a Senior SEO and Digital Visibility Analyst.

TARGET BUSINESS
===============

Name: {name}
Website: {website}
Industry: {industry}
Location: {location}


SEARCH DATA
===========

TARGET:
{target_search}

LOCAL BUSINESSES:
{local_search}

MARKET LEADERS:
{market_search}


INSTRUCTIONS
============

1. Analyze the target business using the available evidence.

2. Identify up to 5 real independent local competitors
   from the supplied search data.

3. Identify up to 5 relevant market leaders.

4. Do not invent companies.

5. Scores should be evidence-based estimates from 0 to 100.

6. Do not use emojis.

7. Return ONLY valid JSON.


JSON FORMAT
===========

{{
    "target": {{
        "name": "{name}",
        "score": 0
    }},

    "local_competitors": [
        {{
            "name": "Competitor",
            "score": 0
        }}
    ],

    "market_leaders": [
        {{
            "name": "Market Leader",
            "score": 0
        }}
    ],

    "insight_summary": "Two sentence summary of the digital visibility situation."
}}

Return ONLY JSON.
"""

        print("[VISIBILITY] Sending data to Groq...")

        return await self.generate_json(
            prompt,
            temperature=0.3
        )


# ==========================================================
# INITIALIZE ENGINE
# ==========================================================

try:

    engine = GrowthPilotEngine()

    print(
        f"[STARTUP] GrowthPilot using model: "
        f"{engine.model}"
    )

except Exception as e:

    print(
        f"[STARTUP ERROR] {str(e)}"
    )

    engine = None


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "service": "GrowthPilot AI",
        "model": engine.model if engine else "not configured"
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy" if engine else "error",
        "model": engine.model if engine else None,
        "groq_configured": engine is not None
    }


# ==========================================================
# GROWTH ANALYSIS API
# ==========================================================

@app.post("/api/growth-analysis")
async def handle_growth_analysis(
    payload: AnalysisRequest
):

    if engine is None:

        raise HTTPException(
            status_code=500,
            detail="GrowthPilot backend is not configured. Check GROQ_API_KEY."
        )

    try:

        result = await engine.run_full_analysis(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location,
            goal=payload.goal
        )

        return result

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"[GROWTH ENDPOINT ERROR] "
            f"{type(e).__name__}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Growth analysis failed: {str(e)}"
        )


# ==========================================================
# VISIBILITY AUDIT API
# ==========================================================

@app.post("/api/visibility-audit")
async def handle_visibility_audit(
    payload: AnalysisRequest
):

    if engine is None:

        raise HTTPException(
            status_code=500,
            detail="GrowthPilot backend is not configured. Check GROQ_API_KEY."
        )

    try:

        result = await engine.run_visibility_audit(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location
        )

        return result

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"[VISIBILITY ENDPOINT ERROR] "
            f"{type(e).__name__}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Visibility audit failed: {str(e)}"
        )
