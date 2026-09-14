import asyncio
import subprocess

from fastapi import APIRouter, BackgroundTasks, HTTPException
from schemas.youtube import YoutubeRequest
from schemas.job import Job, JobStatus, JobResult, JobSegment
from services import job_repository
from services.youtube_service import extract_video_id, get_transcript_data
from services.demo_gloss_override import DEMO_GLOSS_OVERRIDE, build_display_sequence_from_codes
from services.llm_gloss_service import convert_to_gloss, GlossConversionError
from services.clip_resolver import resolve_clip_path, VIDEOS_DIR
from services.timeline_builder import build_timeline
from services.video_merger import merge_timeline_to_video, MISSING_CLIP_FALLBACK_SECONDS

router = APIRouter()

# ponytail: 이번 시연 목적상 고정 파일명 사용. 실제 서비스에서는 job_id 기반
# 파일명으로 변경 필요 (동시에 여러 job이 돌면 서로 덮어씀).
DEMO_OUTPUT_FILENAME = "presentation_demo.mp4"


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

    # KSL_CONVERTING: 시안 문장은 DEMO_GLOSS_OVERRIDE로 바로 대체하고,
    # 그 외 문장만 실제 Gemini 호출로 gloss 변환한다.
    job_repository.update_job(job_id, status=JobStatus.KSL_CONVERTING)

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
            gloss_sequence = await asyncio.to_thread(convert_to_gloss, seg.source_text)
        except GlossConversionError as e:
            job_repository.update_job(
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
    job_repository.update_job(job_id, status=JobStatus.SIGN_MAPPING)

    job_repository.update_job(job_id, status=JobStatus.TIMELINE_BUILDING)

    try:
        timeline = await asyncio.to_thread(build_timeline, timeline_segments, _get_clip_duration)
        video_url = await asyncio.to_thread(merge_timeline_to_video, timeline, DEMO_OUTPUT_FILENAME)
    except Exception as e:
        job_repository.update_job(
            job_id,
            status=JobStatus.FAILED,
            failed_stage="TIMELINE_BUILDING",
            error_code="TIMELINE_BUILD_ERROR",
            error_message=str(e),
        )
        return

    result = JobResult(transcript=full_text, segments=segments, video_url=video_url)

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
