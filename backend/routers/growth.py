from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.growth_service import GrowthOrchestrator

router = APIRouter()
# Instantiate the synchronized async execution pipeline engine
orchestrator = GrowthOrchestrator()

class GrowthRequest(BaseModel):
    business_name: str
    website: str
    industry: str
    location: str
    goal: str

@router.post("/growth-analysis")
async def analyze_business(request: GrowthRequest):
    try:
        # Run the sequential multi-agent orchestration chain
        report = await orchestrator.run_full_pipeline(
            business_name=request.business_name,
            website=request.website,
            industry=request.industry,
            location=request.location,
            goal=request.goal
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))