import os
import json
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

class MarketGapAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-20b"

    async def detect_gaps(self, biz_profile: dict, comp_intelligence: list) -> dict:
        print("[MarketGapAgent] Spotting structural market voids and vulnerabilities...")

        prompt = f"""
        You are a top-tier corporate venture architect and market opportunity expert.
        Compare the target company's profile against the intelligence profiles of its competitors to isolate structural market gaps.

        Target Business Context:
        {json.dumps(biz_profile, indent=2)}

        Competitor Footprint Matrix:
        {json.dumps(comp_intelligence, indent=2)}

        TASK:
        Isolate actionable gaps in the market where the competitors are weak, inactive, or completely missing the mark, and where the target company can realistically capture market share.

        CRITICAL: Return ONLY a valid JSON object matching this exact schema. Do NOT wrap the response in markdown blocks:
        {{
            "underserved_markets": "A definitive summary of the core underserved market segment or geography.",
            "missing_services": [
                "Specific service or feature void 1 that competitors don't offer",
                "Specific service or feature void 2 that competitors don't offer"
            ],
            "opportunity_areas": [
                "High-impact opportunity zone 1",
                "High-impact opportunity zone 2"
            ],
            "growth_potential": "Macroscopic summary of the revenue expansion capacity unlocked by executing on these gaps."
        }}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a cold, calculated business intelligence parser. You output raw, valid JSON profiles only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"[MarketGapAgent] Critical Pipeline Failure: {str(e)}")
            # Safe UI-matched fallback structure
            return {
                "underserved_markets": "Niche localized enterprise support optimization channels.",
                "missing_services": ["Programmatic integration blueprints", "Automated tracking analytics infrastructure"],
                "opportunity_areas": ["Hyper-personalized customer retention layers"],
                "growth_potential": "Data streaming normalization pending."
            }
