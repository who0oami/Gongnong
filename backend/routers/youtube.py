from fastapi import APIRouter, HTTPException
from schemas.youtube import YoutubeRequest, YoutubeResponse
from services.youtube_service import extract_video_id, get_transcript_text

router = APIRouter()

@router.post("/translate", response_model=YoutubeResponse)
def translate(request: YoutubeRequest):
    video_id = extract_video_id(request.url)

    if video_id is None:
        raise HTTPException(status_code=400, detail="URL에서 영상 ID를 찾을 수 없습니다.")

    try:
        transcript = get_transcript_text(video_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return YoutubeResponse(received_url=request.url, transcript=transcript)