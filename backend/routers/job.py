import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from schemas.youtube import YoutubeRequest
from schemas.job import Job, JobStatus, JobSegment
from services import job_repository
from services.youtube_service import extract_video_id, get_transcript_data

router = APIRouter()


async def process_job(job_id: str, url: str) -> None:
    db = SessionLocal()
    try:
        video_id = extract_video_id(url)

        if video_id is None:
            job_repository.update_translation_job_db(
                db,
                job_id,
                status=JobStatus.FAILED,
                error_message="URL에서 영상 ID를 찾을 수 없습니다.",
            )
            return

        job_repository.update_translation_job_db(
            db,
            job_id,
            status=JobStatus.TRANSCRIPTING,
        )

        try:
            _, raw_segments = await asyncio.to_thread(get_transcript_data, video_id)
        except ValueError as e:
            job_repository.update_translation_job_db(
                db,
                job_id,
                status=JobStatus.FAILED,
                error_message=str(e),
            )
            return

        segments = [
            JobSegment(start=seg["start"], end=seg["end"], source_text=seg["text"])
            for seg in raw_segments
        ]

        translation_job = job_repository.get_translation_job_db(db, job_id)
        if translation_job is None:
            return

        job_repository.create_transcript_segments_db(
            db,
            translation_job_id=translation_job.id,
            segments=segments,
        )
        job_repository.update_translation_job_db(
            db,
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(),
        )
    finally:
        db.close()


@router.post("/translate/jobs", response_model=Job, status_code=202)
async def create_translation_job(
    request: YoutubeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    video_id = extract_video_id(request.url)

    if video_id is None:
        raise HTTPException(
            status_code=400,
            detail="URL에서 영상 ID를 찾을 수 없습니다.",
        )

    video = job_repository.get_or_create_video_db(
        db,
        source_url=request.url,
        youtube_video_id=video_id,
    )
    translation_job = job_repository.create_translation_job_db(
        db,
        video_id=video.id,
    )

    job = Job(
        job_id=str(translation_job.public_id),
        status=JobStatus(translation_job.status),
        url=request.url,
    )

    background_tasks.add_task(process_job, job.job_id, request.url)

    return job


@router.get("/translate/jobs/{job_id}", response_model=Job)
async def get_translation_job(job_id: str, db: Session = Depends(get_db)):
    job_with_video = job_repository.get_translation_job_with_video_db(db, job_id)

    if job_with_video is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")

    translation_job, video = job_with_video
    return Job(
        job_id=str(translation_job.public_id),
        status=JobStatus(translation_job.status),
        url=video.source_url,
        error_message=translation_job.error_message,
    )
