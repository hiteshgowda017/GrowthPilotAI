import os
import json
import asyncio
from ddgs import DDGS
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()


class VisibilityIntelligenceAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    def _scrape_brand_mentions(self, target: str) -> int:
        try:
            with DDGS() as ddgs:
                return len(list(ddgs.text(f'"{target}"', max_results=20)))
        except Exception as e:
            print(f"[VisibilityAgent] DDGS search failed for {target}: {e}")
            return 0

    async def _analyze_target(self, target: str):
        mention_count = await asyncio.to_thread(
            self._scrape_brand_mentions, target
        )
        return {
            "company": target,
            "score": min(100, mention_count * 5),
            "mention_count": mention_count,
        }

    async def run_audit(self, brand_name: str, competitors: list) -> dict:
        targets = [brand_name] + [
            str(c).strip() for c in competitors if str(c).strip()
        ]
        audit_results = await asyncio.gather(
            *(self._analyze_target(target) for target in targets)
        )

        brand_data = next(
            (x for x in audit_results if x["company"] == brand_name),
            {"company": brand_name, "score": 0, "mention_count": 0},
        )
        competitor_matrix = [
            x for x in audit_results if x["company"] != brand_name
        ]

        prompt = f"""
You are a digital growth architect specializing in search visibility.

Target Brand: {brand_name}
Target Visibility Score: {brand_data["score"]}/100

Competitor Comparison:
{json.dumps(competitor_matrix, indent=2)}

Provide exactly 2 practical recommendations for improving relevant search
visibility, keyword indexing and online brand mentions.

Return ONLY valid JSON:
{{"recommendations":["Recommendation 1","Recommendation 2"]}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content
            ai_insights = json.loads(content) if content else {}
        except Exception as e:
            print(f"[VisibilityAgent] AI recommendation failed: {e}")
            ai_insights = {}

        recommendations = ai_insights.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = []

        return {
            "visibility_score": brand_data["score"],
            "competitor_comparison": competitor_matrix,
            "recommendations": recommendations[:2],
        }
