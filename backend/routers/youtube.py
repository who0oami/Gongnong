from fastapi import APIRouter
from schemas.youtube import YoutubeRequest

router = APIRouter()

@router.post("/translate")
def translate(request: YoutubeRequest):
    return {"received_url": request.url}