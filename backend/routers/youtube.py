from fastapi import APIRouter
from schemas.youtube import YoutubeRequest, YoutubeResponse

router = APIRouter()

@router.post("/translate", response_model=YoutubeResponse)
def translate(request: YoutubeRequest):
    return YoutubeResponse(received_url=request.url)