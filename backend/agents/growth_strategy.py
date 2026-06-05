import os
import json
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

class GrowthStrategyAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    async def generate_roadmap(self, biz_profile: dict, market_gaps: dict, goal: str) -> dict:
        print("[GrowthStrategyAgent] Synthesizing Brand Dominance Roadmap...")

        prompt = f"""
        You are a Tier-1 Growth Architect. 
        Based on the target brand's profile and the structural market voids identified, generate a ruthless, actionable execution roadmap. 
        The ideology here is BRAND DOMINANCE. How does the target company exploit these gaps to crush competitors and scale their valuation?

        Brand Profile:
        {json.dumps(biz_profile, indent=2)}

        Market Voids to Exploit:
        {json.dumps(market_gaps, indent=2)}

        Primary Objective: {goal}

        CRITICAL: Return ONLY a valid JSON object matching this exact schema:
        {{
            "quick_wins": ["One highly specific tactical move they can execute this week to steal market share."],
            "plan_30_day": ["One major strategic campaign or product pivot to launch within 30 days."],
            "plan_90_day": ["The core scaling mechanism to solidify their brand dominance over the next quarter."],
            "expected_impact": "A powerful 1-sentence projection of how this roadmap increases their corporate valuation and market cap."
        }}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise JSON data parser. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"[GrowthStrategyAgent] Error: {str(e)}")
            return {
                "quick_wins": ["Optimize current conversion funnels based on initial audit data."],
                "plan_30_day": ["Deploy targeted visibility campaigns into competitor blind spots."],
                "plan_90_day": ["Scale infrastructure to support captured market voids."],
                "expected_impact": "Incremental revenue expansion and stabilized market positioning."
            }