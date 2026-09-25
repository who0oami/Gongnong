from services.timing import Metrics, emit_metrics

import logging
import os
import re
from pathlib import Path

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
)
from boto3.exceptions import Boto3Error

logger = logging.getLogger(__name__)
# SEN only: its S3 key convention has not been defined yet.
VIDEOS_DIR = Path(__file__).resolve().parent.parent / "static" / "videos"


class ClipStorageUnavailable(RuntimeError):
    """The configured avatar clip storage cannot be accessed."""


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _create_s3_client():
    """Prefer explicit deploy credentials so an accidental local profile cannot shadow them."""
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if access_key and secret_key:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=os.getenv("AWS_SESSION_TOKEN") or None,
            region_name=os.getenv("AWS_DEFAULT_REGION") or None,
        )
        return session.client("s3")
    return boto3.client("s3")


def resolve_clip_path(code: str, clip_paths: dict[str, Path | None]) -> Path | None:
    """Read the prepared job mapping without downloading or rebuilding paths."""
    return clip_paths.get(code)


def resolve_clips(display_sequence: list[dict], work_dir: Path) -> dict[str, Path | None]:
    """Prepare unique clips before timing. Caller owns work_dir through merging."""
    stats = Metrics()
    try:
        resolved: dict[str, Path | None] = {}
        bucket = os.getenv("S3_CLIP_BUCKET", "").strip()
        client = None
        has_word = any(
            item.get("type") == "avatar" and re.fullmatch(r"WORD\d+", item.get("code", ""))
            for item in display_sequence
        )
        if has_word and not bucket:
            raise ClipStorageUnavailable("S3_CLIP_BUCKET이 설정되지 않았습니다.")
        for item in display_sequence:
            if item["type"] != "avatar":
                continue
            stats.counts["avatar_items"] += 1
            code = item["code"]
            if code in resolved:
                continue
            resolved[code] = None
            if re.fullmatch(r"SEN\d+", code):
                path = VIDEOS_DIR / f"{code}.mp4"
                resolved[code] = path if path.is_file() else None
                continue
            if not re.fullmatch(r"WORD\d+", code):
                continue
            stats.counts["unique_words"] += 1
            path = work_dir / f"{code}.mp4"
            try:
                if client is None:
                    try:
                        client = _create_s3_client()
                    except (BotoCoreError, ClientError, Boto3Error) as exc:
                        stats.counts["failed"] += 1
                        if isinstance(exc, ProfileNotFound):
                            message = "Render의 AWS_PROFILE을 삭제하고 AWS Access Key 환경 변수를 설정해 주세요."
                        else:
                            message = f"S3 클라이언트를 생성하지 못했습니다: {type(exc).__name__}"
                        raise ClipStorageUnavailable(message) from exc
                try:
                    with stats.measure("downloads"):
                        client.download_file(bucket, f"clips/word/{code}.mp4", str(path))
                except Exception:
                    stats.counts["failed"] += 1
                    raise
                else:
                    stats.counts["success"] += 1
                resolved[code] = path
            except ClientError as exc:
                if _client_error_code(exc) not in {"404", "NoSuchKey", "NotFound"}:
                    raise ClipStorageUnavailable(
                        f"S3 클립 저장소에 접근하지 못했습니다: {_client_error_code(exc) or type(exc).__name__}"
                    ) from exc
                logger.warning("Clip download failed for %s: %s", code, type(exc).__name__)
                path.unlink(missing_ok=True)
            except (NoCredentialsError, PartialCredentialsError, ProfileNotFound,
                    BotoCoreError, Boto3Error, OSError) as exc:
                path.unlink(missing_ok=True)
                raise ClipStorageUnavailable(
                    f"S3 클립 저장소에 접근하지 못했습니다: {type(exc).__name__}"
                ) from exc
        return resolved
    finally:
        emit_metrics("S3 Timing", f"avatar_items={stats.counts['avatar_items']} "
                     f"unique_words={stats.counts['unique_words']} downloads={stats.counts['downloads']} "
                     f"success={stats.counts['success']} failed={stats.counts['failed']} "
                     f"total={stats.seconds['downloads']:.2f}s")
