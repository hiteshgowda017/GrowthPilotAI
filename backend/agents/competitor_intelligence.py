import os
import json
import asyncio
from groq import AsyncGroq
from dotenv import load_dotenv

# Import your existing scraper. We will run it in a non-blocking thread.
from agents.web_research import research_company 

load_dotenv()

class CompetitorIntelligenceAgent:
    def __init__(self):
        # Asynchronous Groq client for parallel competitor processing
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-20b"

    async def _analyze_single(self, competitor_name: str, target_biz: dict):
        """Internal method to research and analyze a single competitor."""
        try:
            print(f"[IntelligenceAgent] Initiating deep research on: {competitor_name}")
            
            # Run the synchronous web research in a background thread to keep the server fast
            research_data = await asyncio.to_thread(research_company, competitor_name)

            prompt = f"""
            You are a senior competitive intelligence analyst.
            Compare the target business against this competitor using the provided live research data.

            Target Business Context:
            Name: {target_biz.get('summary', 'Unknown')}
            Goal: {target_biz.get('growth_objective', 'Unknown')}

            COMPETITOR TO ANALYZE: {competitor_name}
            LIVE RESEARCH DATA: {research_data}

            Output a strict JSON object profiling this competitor. Do not use markdown (like ```json).
            It must exactly match this schema for the frontend UI:
            {{
                "name": "{competitor_name}",
                "type": "Direct or Indirect",
                "usp": "One sentence summarizing their Unique Selling Proposition",
                "strengths": "Comma separated list of 2-3 key strengths",
                "weaknesses": "Comma separated list of 2-3 key weaknesses",
                "marketing_presence": "Summary of their digital footprint",
                "threat_score": 85  // Integer between 1 and 100
            }}
            """

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise data-extraction AI that outputs only raw, valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1 # Very low temperature for analytical accuracy
            )

            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"[IntelligenceAgent] Error analyzing {competitor_name}: {str(e)}")
            # Fallback JSON so a single competitor failure doesn't crash the whole report
            return {
                "name": competitor_name,
                "type": "Unknown",
                "usp": "Not verified",
                "strengths": "Not verified",
                "weaknesses": "Not verified",
                "marketing_presence": "Evidence unavailable",
                "threat_score": 0
            }

    async def profile_competitors(self, competitors: list, target_biz: dict):
        """
        Takes a list of competitor names and processes them concurrently.
        This reduces a 30-second sequential task into a 10-second parallel task.
        """
        # If the incoming list is empty, provide a fallback
        if not competitors:
            competitors = ["Industry Leader 1", "Industry Leader 2"]
            
        print(f"[IntelligenceAgent] Spinning up parallel analysis for {len(competitors)} competitors...")
        
        # Create asynchronous tasks for all competitors
        tasks = [self._analyze_single(comp, target_biz) for comp in competitors]
        
        # Execute all tasks at the exact same time
        results = await asyncio.gather(*tasks)
        
        return results
