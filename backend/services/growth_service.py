import asyncio
import sys
import os
from fastapi import HTTPException

# Force parent directory into sys.path to locate the 'agents' package easily
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.business_analysis import BusinessAnalysisAgent
from agents.competitor_research import CompetitorResearchAgent
from agents.competitor_intelligence import CompetitorIntelligenceAgent
from agents.market_gap import MarketGapAgent
from agents.growth_strategy import GrowthStrategyAgent

class GrowthOrchestrator:
    def __init__(self):
        self.business_agent = BusinessAnalysisAgent()
        self.research_agent = CompetitorResearchAgent()
        self.intelligence_agent = CompetitorIntelligenceAgent()
        self.market_gap_agent = MarketGapAgent()
        self.strategy_agent = GrowthStrategyAgent()

    async def run_full_pipeline(self, business_name: str, website: str, industry: str, location: str, goal: str):
        try:
            print(f"[SYSTEM] Initializing GrowthPilot Pipeline for {business_name}...")

            # Phase 1: Business Profile Analysis
            biz_profile = await self.business_agent.analyze(
                name=business_name, website=website, industry=industry, location=location, goal=goal
            )

            # Phase 2: Competitor Discovery (Web Scrape)
            competitor_list = await self.research_agent.discover_competitors(
                industry=industry, location=location
            )

            # Phase 3: Deep Competitor Intelligence Matrix
            comp_intelligence = await self.intelligence_agent.profile_competitors(
                competitors=competitor_list, target_biz=biz_profile
            )

            # Phase 4: Structural Market Gap Extraction
            market_gaps = await self.market_gap_agent.detect_gaps(
                biz_profile=biz_profile, comp_intelligence=comp_intelligence
            )

            # Phase 5: Actionable Growth Roadmap Formulation
            strategy = await self.strategy_agent.generate_roadmap(
                biz_profile=biz_profile, market_gaps=market_gaps, goal=goal
            )

            final_report = {
                "business_analysis": biz_profile,
                "competitors": comp_intelligence,
                "market_gaps": market_gaps,
                "growth_strategy": strategy
            }
            
            print("[SYSTEM] Pipeline Execution Complete Successfully.")
            return final_report

        except Exception as e:
            import traceback
            print(f"[CRITICAL ERROR] Pipeline Failure Context: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Agent orchestration failed: {str(e)}")