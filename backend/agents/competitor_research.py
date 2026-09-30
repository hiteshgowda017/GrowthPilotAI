import os
import json
import asyncio
from ddgs import DDGS
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()


class CompetitorResearchAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    def _scrape_ddg(self, query: str) -> str:
        search_results = []
        try:
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=7):
                    search_results.append(
                        f"Title: {result.get('title', '')} | "
                        f"Snippet: {result.get('body', '')} | "
                        f"Source: {result.get('href', '')}"
                    )
            return "\n".join(search_results)
        except Exception as e:
            print(f"[ResearchAgent] DDGS search failed: {e}")
            return ""

    async def discover_competitors(self, industry: str, location: str) -> list:
        print(f"[ResearchAgent] Live competitor search: {industry} in {location}")

        combined_results = await asyncio.to_thread(
            self._scrape_ddg,
            f"top {industry} companies businesses in {location}",
        )

        if not combined_results:
            return []

        prompt = f"""
You are a competitive intelligence analyst.
Identify up to 3 REAL competitors from the live search results below.

Industry: {industry}
Location: {location}

LIVE SEARCH RESULTS:
{combined_results}

Rules:
- Use only businesses supported by the supplied search results.
- Do not invent companies.
- Ignore blogs, directories, news sites and non-business entities.

Return ONLY:
{{"competitors":["Competitor 1","Competitor 2","Competitor 3"]}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content
            if not content:
                return []

            data = json.loads(content)
            competitors = data.get("competitors", [])
            if not isinstance(competitors, list):
                return []

            return [str(x).strip() for x in competitors if str(x).strip()][:3]

        except Exception as e:
            print(f"[ResearchAgent] Competitor extraction failed: {e}")
            return []
