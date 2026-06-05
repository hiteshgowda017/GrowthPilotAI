from agents.visibility_intelligence import VisibilityIntelligenceAgent

class VisibilityService:
    def __init__(self):
        self.agent = VisibilityIntelligenceAgent()

    async def execute_audit(self, brand_name: str, competitors: list):
        return await self.agent.run_audit(brand_name=brand_name, competitors=competitors)