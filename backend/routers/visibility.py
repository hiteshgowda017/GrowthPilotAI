from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.visibility_service import VisibilityService

router = APIRouter()
visibility_service = VisibilityService()

class VisibilityRequest(BaseModel):
    brand_name: str
    competitors: list

@router.post("/visibility-analysis")
async def run_visibility_audit(request: VisibilityRequest):
    try:
        results = await visibility_service.execute_audit(
            brand_name=request.brand_name,
            competitors=request.competitors
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))