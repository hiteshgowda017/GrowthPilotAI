import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    business_name: str
    website: str
    industry: str
    location: str
    goal: str

class GrowthPilotEngine:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-20b"
    async def robust_search(self, query: str, max_results: int = 3, retries: int = 3) -> str:
        """Universal scraper with retries to ensure real data is pulled."""
        for attempt in range(retries):
            try:
                await asyncio.sleep(1.5 + attempt) 
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
                    if results:
                        return "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
            except Exception:
                continue 
        
        return "SEARCH_BLOCKED"

    # ==========================================================
    # ENGINE 1: UNIVERSAL GROWTH INTELLIGENCE (DYNAMIC SCORING)
    # ==========================================================
    async def run_full_analysis(self, name: str, website: str, industry: str, location: str, goal: str) -> dict:
        print(f"\n=== [INITIATING UNIVERSAL GROWTH ENGINE: {name.upper()}] ===")
        
        clean_url = website.replace("https://", "").replace("http://", "").split('/')[0]

        print("Phase 1: Harvesting dynamic data...")
        site_data = await self.robust_search(f"site:{clean_url} OR \"{name}\" {location} core services")
        comp_data = await self.robust_search(f"top local {industry} competitors in {location}")
        review_data = await self.robust_search(f"\"{name}\" OR top {industry} in {location} customer reviews complaints")
        
        master_prompt = f"""
        You are GrowthPilot AI, an elite Enterprise Growth Consultant.
        Target Client: {name} ({website})
        Industry Context: {industry}
        Geographic Market: {location}
        Client Goal: {goal}

        LIVE SEARCH DATA:
        Target Site Info: {site_data}
        Market Competitors: {comp_data}
        Market Friction/Reviews: {review_data}

        CRITICAL INTELLIGENCE DIRECTIVES:
        1. NO GLOBAL CHAINS: You MUST name 5 REAL, SPECIFIC independent {industry} businesses in {location}. NEVER name global conglomerates.
        2. HYPER-VERBOSITY PROTOCOL: Write massive, exhaustive, multi-sentence paragraphs for EVERY section. Minimum 150 words per phase.
        3. CALCULATE DYNAMIC METRICS: Do NOT use copied or boilerplate numbers. You MUST calculate a unique AI Visibility Score and Vulnerability Score based on the scraped data context.
        
        Return ONLY a JSON object exactly matching this schema (Replace placeholders with calculated values):
        {{
            "metrics": {{
                "market_rank": "Rank #<CALCULATE_RANK> out of <CALCULATE_TOTAL> Local Peers",
                "ai_visibility_score": "<CALCULATE_UNIQUE_SCORE_0_TO_100>",
                "vulnerability_score": "<CALCULATE_UNIQUE_SCORE_0_TO_100>",
                "top_opportunity": "Specific 3-4 word niche"
            }},
            "report_markdown": "# === GrowthPilot Executive Intelligence Report ===\\n\\n## Phase I: Enterprise Structural Audit\\n(Write a massive, 3-paragraph operational teardown of {name} tailored to the {industry} sector.)\\n\\n## Phase II: The Competitive Matrix\\n(List 5 REAL local independent {industry} competitors in {location}. Write a deep dive for EACH.)\\n\\n## Phase III: Operational Intelligence\\n(Write a lengthy analysis of technical/service gaps between {name} and local {industry} competitors.)\\n\\n## Phase IV: Vulnerability & Exploitation Strategy\\n(Select one real local competitor. Define their likely weaknesses. Provide an Attack Strategy.)\\n\\n## Phase V: Market Opportunity Mapping\\n(Identify 3 Untapped Customer Segments specific to {location} for this industry.)\\n\\n## Phase VI: Algorithmic Visibility Index\\n(Write a highly technical paragraph measuring how visible {name} is compared to local peers.)\\n\\n## Phase VII: Strategic Growth Roadmap\\n(Write extensive, multi-sentence explanations for the Quick Wins, 30-Day, 90-Day, and 1-Year plans based on the client's goal: {goal}.)\\n\\n## Phase VIII: The Tactical Battle Plan\\n(Target one specific local competitor. List an incredibly detailed, 5-step concrete execution plan.)"
        }}
        """

        try:
            strategy_res = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You output strictly as JSON. You MUST calculate unique integer scores. No emojis. No hallucinated mega-corporations."},
                    {"role": "user", "content": master_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.45 
            )
            return json.loads(strategy_res.choices[0].message.content)
        except Exception as e:
            print(f"[Growth AI Fatal Error] {str(e)}")
            raise HTTPException(status_code=500, detail="Growth Engine offline or data extraction failed.")

    # ==========================================================
    # ENGINE 2: UNIVERSAL VISIBILITY AUDIT
    # ==========================================================
    async def run_visibility_audit(self, name: str, website: str, industry: str, location: str) -> dict:
        print(f"\n=== [INITIATING UNIVERSAL VISIBILITY AUDIT: {name.upper()}] ===")
        
        print("Phase 1: Harvesting footprint data...")
        local_search = await self.robust_search(f"top independent {industry} businesses in {location} directory")
        global_search = await self.robust_search(f"largest market share global {industry} leaders titans")
        target_search = await self.robust_search(f"\"{name}\" {location} digital presence reviews social media")

        visibility_prompt = f"""
        You are a Senior SEO & Digital Footprint Analyst.
        Target Company: {name} ({website})
        Industry Context: {industry}
        Geographic Market: {location}

        Data Context:
        Target Presence: {target_search}
        Local Peers: {local_search}
        Global Leaders: {global_search}

        CRITICAL INSTRUCTIONS:
        1. Identify exactly 5 REAL, INDEPENDENT local competitors operating in the {industry} space in {location}.
        2. DO NOT INCLUDE GLOBAL CHAINS OR FRANCHISES IN THE LOCAL LIST.
        3. Identify exactly 5 REAL global/national market leaders in the {industry} sector.
        4. CALCULATE A UNIQUE Visibility Score (0 to 100) based on digital footprint strength. Do NOT copy boilerplate numbers. You MUST calculate real, dynamic scores.
        5. STRICT NO-CRASH POLICY: DO NOT USE EMOJIS. DO NOT use markdown code blocks. Output strictly JSON.

        Return strictly as a JSON object matching this exact schema (Replace placeholders with your calculated integers and text):
        {{
            "target": {{ "name": "{name}", "score": <CALCULATE_UNIQUE_SCORE> }},
            "local_competitors": [
                {{ "name": "<Real Independent Local Competitor 1>", "score": <CALCULATE_SCORE_1> }},
                {{ "name": "<Real Independent Local Competitor 2>", "score": <CALCULATE_SCORE_2> }},
                {{ "name": "<Real Independent Local Competitor 3>", "score": <CALCULATE_SCORE_3> }},
                {{ "name": "<Real Independent Local Competitor 4>", "score": <CALCULATE_SCORE_4> }},
                {{ "name": "<Real Independent Local Competitor 5>", "score": <CALCULATE_SCORE_5> }}
            ],
            "market_leaders": [
                {{ "name": "<Global Industry Leader 1>", "score": <CALCULATE_GLOBAL_SCORE_1> }},
                {{ "name": "<Global Industry Leader 2>", "score": <CALCULATE_GLOBAL_SCORE_2> }},
                {{ "name": "<Global Industry Leader 3>", "score": <CALCULATE_GLOBAL_SCORE_3> }},
                {{ "name": "<Global Industry Leader 4>", "score": <CALCULATE_GLOBAL_SCORE_4> }},
                {{ "name": "<Global Industry Leader 5>", "score": <CALCULATE_GLOBAL_SCORE_5> }}
            ],
            "insight_summary": "A 2-sentence expert summary on digital visibility within the {industry} sector."
        }}
        """

        try:
            res = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You output strictly as raw JSON. You MUST calculate dynamic integer scores. No markdown, no emojis."},
                    {"role": "user", "content": visibility_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.35 
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            print(f"[Visibility Audit AI Error] {str(e)}")
            raise HTTPException(status_code=500, detail="Visibility Engine offline. Data extraction failed.")

# ==========================================================
# FASTAPI ROUTER ENDPOINTS
# ==========================================================
engine = GrowthPilotEngine()

@app.post("/api/growth-analysis")
async def handle_growth_analysis(payload: AnalysisRequest):
    try:
        return await engine.run_full_analysis(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location,
            goal=payload.goal
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/visibility-audit")
async def handle_visibility_audit(payload: AnalysisRequest):
    try:
        return await engine.run_visibility_audit(
            name=payload.business_name,
            website=payload.website,
            industry=payload.industry,
            location=payload.location
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
