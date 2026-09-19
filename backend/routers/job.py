import asyncio
import subprocess
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from schemas.youtube import YoutubeRequest
from schemas.job import Job, JobStatus, JobResult, JobSegment
from services import job_repository
from services.youtube_service import extract_video_id
from services.subtitle_pipeline_service import get_corrected_transcript_data
from services.demo_gloss_override import DEMO_GLOSS_OVERRIDE, build_display_sequence_from_codes
from services.llm_gloss_service import convert_to_gloss, GlossConversionError
from services.clip_resolver import resolve_clip_path, VIDEOS_DIR
from services.timeline_builder import build_timeline
from services.video_merger import merge_timeline_to_video, MISSING_CLIP_FALLBACK_SECONDS

router = APIRouter()


def _get_clip_duration(code: str) -> float:
    """video_merger.py의 __main__ 블록과 동일한 방식: 파일이 없으면 고정값,
    있으면 ffprobe로 실제 길이를 조회한다."""
    clip_url = resolve_clip_path(code)
    if clip_url is None:
        return MISSING_CLIP_FALLBACK_SECONDS

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(VIDEOS_DIR / f"{code}.mp4")],
        capture_output=True, text=True, check=True,
    )
    return float(probe.stdout.strip())


async def process_job(job_id: str, url: str) -> None:
    db = SessionLocal()
    try:
        video_id = extract_video_id(url)

        if video_id is None:
            job_repository.update_translation_job_db(
                db,
                job_id,
                status=JobStatus.FAILED,
                failed_stage="TRANSCRIPTING",
                error_code="INVALID_URL",
                error_message="URL에서 영상 ID를 찾을 수 없습니다.",
            )
            return

        job_repository.update_translation_job_db(db, job_id, status=JobStatus.TRANSCRIPTING)

        try:
            transcript_data = await asyncio.to_thread(get_corrected_transcript_data, url)
        except ValueError as e:
            job_repository.update_translation_job_db(
                db,
                job_id,
                status=JobStatus.FAILED,
                failed_stage="TRANSCRIPTING",
                error_code="TRANSCRIPT_ERROR",
                error_message=str(e),
            )
            return

        full_text = transcript_data["transcript"]
        raw_segments = transcript_data["segments"]
        segments = [
            JobSegment(
                start=seg["start"],
                end=seg["end"],
                source_text=seg["text"],
                corrected_text=seg.get("corrected_text"),
            )
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

        # KSL_CONVERTING: 시안 문장은 DEMO_GLOSS_OVERRIDE로 바로 대체하고,
        # 그 외 문장만 실제 Gemini 호출로 gloss 변환한다.
        job_repository.update_translation_job_db(db, job_id, status=JobStatus.KSL_CONVERTING)

        timeline_segments: list[dict] = []

        for seg in segments:
            override_codes = DEMO_GLOSS_OVERRIDE.get(seg.source_text)

            if override_codes is not None:
                timeline_segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "display_sequence": build_display_sequence_from_codes(override_codes),
                })
                continue

            try:
                gloss_sequence = await asyncio.to_thread(
                    convert_to_gloss,
                    seg.corrected_text or seg.source_text,
                )
            except GlossConversionError as e:
                job_repository.update_translation_job_db(
                    db,
                    job_id,
                    status=JobStatus.FAILED,
                    failed_stage="KSL_CONVERTING",
                    error_code="GLOSS_CONVERSION_ERROR",
                    error_message=str(e),
                )
                return

            timeline_segments.append({
                "start": seg.start,
                "end": seg.end,
                "gloss_sequence": gloss_sequence,
            })

        # SIGN_MAPPING: 실제 아바타 코드 매칭(gloss -> word/sen code)은
        # build_timeline 내부에서 build_display_sequence를 통해 이뤄진다.
        job_repository.update_translation_job_db(db, job_id, status=JobStatus.SIGN_MAPPING)

        job_repository.update_translation_job_db(db, job_id, status=JobStatus.TIMELINE_BUILDING)

        try:
            timeline = await asyncio.to_thread(build_timeline, timeline_segments, _get_clip_duration)
            video_url = await asyncio.to_thread(
                merge_timeline_to_video,
                timeline,
                f"{job_id}.mp4",
            )
        except Exception as e:
            job_repository.update_translation_job_db(
                db,
                job_id,
                status=JobStatus.FAILED,
                failed_stage="TIMELINE_BUILDING",
                error_code="TIMELINE_BUILD_ERROR",
                error_message=str(e),
            )
            return

        result = JobResult(transcript=full_text, segments=segments, video_url=video_url)

        job_repository.update_translation_job_db(
            db,
            job_id,
            status=JobStatus.COMPLETED,
            result_video_url=video_url,
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
    transcript_segments = job_repository.get_transcript_segments_db(
        db,
        translation_job.id,
    )
    segments = [
        JobSegment(
            start=segment.start_ms / 1000,
            end=segment.end_ms / 1000,
            source_text=segment.source_text,
            corrected_text=segment.corrected_text,
            ksl_text=segment.ksl_text,
        )
        for segment in transcript_segments
    ]
    status = JobStatus(translation_job.status)
    result = None
    if status == JobStatus.COMPLETED or translation_job.result_video_url:
        result = JobResult(
            transcript=" ".join(segment.source_text for segment in segments),
            segments=segments,
            video_url=translation_job.result_video_url,
        )

    return Job(
        job_id=str(translation_job.public_id),
        status=status,
        url=video.source_url,
        result=result,
        failed_stage=translation_job.failed_stage,
        error_code=translation_job.error_code,
        error_message=translation_job.error_message,
    )
