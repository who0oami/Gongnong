import asyncio
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models.user import User
from routers.auth import get_current_user_optional
from schemas.youtube import YoutubeRequest
from schemas.job import Job, JobStatus, JobResult, JobSegment
from services import job_repository
from services.timing import time_job, time_stage, profile_render, measure, render_metrics, emit_metrics
from services.youtube_service import extract_video_id
from services.subtitle_pipeline_service import get_corrected_transcript_data
from services.demo_gloss_override import DEMO_GLOSS_OVERRIDE, build_display_sequence_from_codes
from services.ksl_converter import KSLConversionError
from services.llm_gloss_service import GeminiKSLConverter, get_gloss_batch_size
from services.clip_resolver import resolve_clip_path, resolve_clips
from services.gloss_matcher import build_display_sequence
from services.timeline_builder import build_timeline
from services.video_merger import merge_timeline_to_video, MISSING_CLIP_FALLBACK_SECONDS

router = APIRouter()
ksl_converter: GeminiKSLConverter = GeminiKSLConverter()


def _get_clip_duration(code: str, clip_paths: dict[str, Path | None]) -> float:
    """Probe the prepared job file, or use the missing-clip fallback duration."""
    clip_path = resolve_clip_path(code, clip_paths)
    if clip_path is None:
        return MISSING_CLIP_FALLBACK_SECONDS

    with measure(render_metrics, "FFPROBE_DURATION"):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path)],
            capture_output=True, text=True, check=True,
        )
    return float(probe.stdout.strip())


@profile_render
def _render_job_video(job_id: str, segments: list[dict]) -> str:
    # A single worker owns the lifetime even if the awaiting task is cancelled.
    with tempfile.TemporaryDirectory(prefix="ksl_job_") as temp_dir:
        with time_stage("SIGN_MAPPING", job_id), measure(render_metrics, "DISPLAY_SEQUENCE_PREP"):
            prepared = [
                {**seg, "display_sequence": seg["display_sequence"]
                 if "display_sequence" in seg else build_display_sequence(seg["gloss_sequence"])}
                for seg in segments
            ]
        with time_stage("TIMELINE_BUILDING", job_id):
            with measure(render_metrics, "S3_CLIP_RESOLVE"):
                clip_paths = resolve_clips(
                    [item for seg in prepared for item in seg["display_sequence"]], Path(temp_dir),
                )
            avatar_items = [item for seg in prepared for item in seg["display_sequence"] if item["type"] == "avatar"]
            emit_metrics("Render Stats", f"segments={len(prepared)} avatar_items={len(avatar_items)} "
                         f"unique_avatar_codes={len({item['code'] for item in avatar_items})} "
                         f"missing_clips={sum(clip_paths.get(item['code']) is None for item in avatar_items)}", job_id)
            durations = {}

            def get_duration(code: str) -> float:
                if code not in durations:
                    durations[code] = _get_clip_duration(code, clip_paths)
                else:
                    render_metrics.get().counts["cache_hits"] += 1
                return durations[code]

            with measure(render_metrics, "TIMELINE_CALC"):
                timeline = build_timeline(prepared, get_duration)
            with measure(render_metrics, "VIDEO_MERGE"):
                return merge_timeline_to_video(timeline, f"{job_id}.mp4", clip_paths)


@time_job
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

        with time_stage("KSL_CONVERTING") as gloss_timer:
            timeline_segments: list[dict] = [
                {"start": seg.start, "end": seg.end} for seg in segments
            ]
            pending = []
            for index, seg in enumerate(segments):
                override_codes = DEMO_GLOSS_OVERRIDE.get(seg.source_text)
                if override_codes is not None:
                    print(f"[Gloss] {index + 1}/{len(segments)} DEMO override 적용", flush=True)
                    timeline_segments[index]["display_sequence"] = build_display_sequence_from_codes(override_codes)
                else:
                    pending.append((index, seg.corrected_text or seg.source_text))

            batch_size = get_gloss_batch_size()
            batch_count = (len(pending) + batch_size - 1) // batch_size
            for offset in range(0, len(pending), batch_size):
                chunk = pending[offset:offset + batch_size]
                batch_number = offset // batch_size + 1
                # List exact original positions when overrides leave gaps.
                positions = [index + 1 for index, _ in chunk]
                label = (f"{positions[0]}-{positions[-1]}"
                         if positions == list(range(positions[0], positions[-1] + 1))
                         else ",".join(map(str, positions)))
                print(f"[Gloss Batch] {batch_number}/{batch_count} 변환 시작 (segments {label})", flush=True)
                try:
                    gloss_sequences = await asyncio.to_thread(
                        ksl_converter.convert_batch, [text for _, text in chunk],
                    )
                    if len(gloss_sequences) != len(chunk):
                        raise KSLConversionError("입력과 출력 segment 수가 다릅니다")
                except KSLConversionError as e:
                    gloss_timer.failed = True
                    job_repository.update_translation_job_db(
                        db,
                        job_id,
                        status=JobStatus.FAILED,
                        failed_stage="KSL_CONVERTING",
                        error_code="GLOSS_CONVERSION_ERROR",
                        error_message=str(e),
                    )
                    return
                for (index, _), gloss_sequence in zip(chunk, gloss_sequences):
                    timeline_segments[index]["gloss_sequence"] = gloss_sequence
                print(f"[Gloss Batch] {batch_number}/{batch_count} 변환 완료", flush=True)

        # The render worker maps and downloads clips before timeline calculation.
        job_repository.update_translation_job_db(db, job_id, status=JobStatus.SIGN_MAPPING)

        job_repository.update_translation_job_db(db, job_id, status=JobStatus.TIMELINE_BUILDING)

        try:
            video_url = await asyncio.to_thread(
                _render_job_video, job_id, timeline_segments,
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
    current_user: User | None = Depends(get_current_user_optional),
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
    # No token, or an invalid/expired one, means an anonymous job (user_id stays null) — it still
    # runs end to end, it just never shows up in anyone's GET /history.
    translation_job = job_repository.create_translation_job_db(
        db,
        video_id=video.id,
        user_id=current_user.id if current_user else None,
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
