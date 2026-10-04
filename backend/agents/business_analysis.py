import os
import json
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

class BusinessAnalysisAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-20b"

    async def analyze(self, name: str, website: str, industry: str, location: str, goal: str) -> dict:
        print(f"[BusinessAnalysisAgent] Initiating Deep Brand & Valuation Analysis for {name}...")

        prompt = f"""
        You are an elite corporate strategist and brand valuation expert.
        Analyze the following target company. Your primary focus is on THEIR brand equity, their industry positioning, and their unique economic moat.

        Target Company: {name}
        Domain: {website}
        Industry: {industry}
        Location/Market: {location}
        Core Objective: {goal}

        TASK: 
        Deconstruct this brand. Why are they valuable? What is their current market position? Who is their high-value target audience?

        CRITICAL: Return ONLY a valid JSON object matching this exact schema:
        {{
            "summary": "A powerful 2-sentence executive summary of the brand's core value proposition.",
            "market_position": "The brand's current dominance level (e.g., 'Emerging Disruptor', 'Legacy Market Leader').",
            "target_audience": "The specific, high-ticket demographic or B2B sector they own.",
            "growth_objective": "A synthesized, professional restatement of their core operational goal."
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
            print(f"[BusinessAnalysisAgent] Extraction Error: {str(e)}")
            return {
                "summary": "Live AI business analysis was unavailable; no unsupported company claims were generated.",
                "market_position": "Not verified",
                "target_audience": "Not verified",
                "growth_objective": goal
            }
