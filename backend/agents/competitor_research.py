import os
import json
import asyncio
from duckduckgo_search import DDGS
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

class CompetitorResearchAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def _scrape_ddg(self, query: str) -> str:
        """Synchronous scraping function to be offloaded to a thread."""
        search_results = []
        try:
            with DDGS() as ddgs:
                # Limit to 7 to keep the context window tight and fast
                results = ddgs.text(query, max_results=7)
                for result in results:
                    title = result.get("title", "")
                    body = result.get("body", "")
                    search_results.append(f"Title: {title} | Snippet: {body}")
            return "\n".join(search_results)
        except Exception as e:
            print(f"[ResearchAgent] DuckDuckGo Scrape Failed: {str(e)}")
            return ""

    async def discover_competitors(self, industry: str, location: str) -> list:
        print(f"[ResearchAgent] Deploying live web scrapers for {industry} in {location}...")
        
        search_query = f"top {industry} companies businesses in {location}"
        
        # Offload the blocking web scraper to a background thread
        combined_results = await asyncio.to_thread(self._scrape_ddg, search_query)

        if not combined_results:
             return ["Market Leader A", "Market Leader B", "Market Leader C"] # Safe fallback

        prompt = f"""
        You are a senior competitive intelligence analyst.
        Your job is to identify the top 3 REAL competitors from the provided live search data.

        Target Market Context:
        Industry: {industry}
        Location: {location}

        LIVE SEARCH RESULTS:
        {combined_results}

        TASK:
        Extract exactly 3 real, direct competitors or market leaders from the text.
        Ignore blog articles, directories (like Yelp/G2), news sites, and non-business entities.

        CRITICAL: Return ONLY a valid JSON object matching this exact schema:
        {{
            "competitors": ["Competitor Name 1", "Competitor Name 2", "Competitor Name 3"]
        }}
        Do NOT wrap the response in markdown.
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise data-extraction AI that outputs only raw, valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1 # Very low for deterministic data extraction
            )

            data = json.loads(response.choices[0].message.content)
            
            # Extract and return just the flat list of names for the Orchestrator
            competitor_list = data.get("competitors", [])
            print(f"[ResearchAgent] Identified valid targets: {competitor_list}")
            
            return competitor_list[:3] # Ensure we only pass 3 targets downstream to maintain speed
            
        except Exception as e:
            print(f"[ResearchAgent] LLM Extraction Error: {str(e)}")
            return ["Primary Competitor", "Secondary Competitor", "Tertiary Competitor"]