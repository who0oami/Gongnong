import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from schemas.youtube import YoutubeRequest
from schemas.job import Job, JobStatus, JobResult, JobSegment
from services import job_repository
from services.youtube_service import extract_video_id, get_transcript_data

router = APIRouter()


async def process_job(job_id: str, url: str) -> None:
    video_id = extract_video_id(url)

    if video_id is None:
        job_repository.update_job(
            job_id,
            status=JobStatus.FAILED,
            failed_stage="TRANSCRIPTING",
            error_code="INVALID_URL",
            error_message="URL에서 영상 ID를 찾을 수 없습니다.",
        )
        return

    job_repository.update_job(job_id, status=JobStatus.TRANSCRIPTING)

    try:
        full_text, raw_segments = await asyncio.to_thread(get_transcript_data, video_id)
    except ValueError as e:
        job_repository.update_job(
            job_id,
            status=JobStatus.FAILED,
            failed_stage="TRANSCRIPTING",
            error_code="TRANSCRIPT_ERROR",
            error_message=str(e),
        )
        return

    segments = [
        JobSegment(start=seg["start"], end=seg["end"], source_text=seg["text"])
        for seg in raw_segments
    ]

    result = JobResult(transcript=full_text, segments=segments)

    job_repository.update_job(job_id, status=JobStatus.COMPLETED, result=result)


@router.post("/translate/jobs", response_model=Job, status_code=202)
async def create_translation_job(request: YoutubeRequest, background_tasks: BackgroundTasks):
    job = job_repository.create_job(url=request.url)
    background_tasks.add_task(process_job, job.job_id, request.url)

    return job


@router.get("/translate/jobs/{job_id}", response_model=Job)
async def get_translation_job(job_id: str):
    job = job_repository.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")

    return job