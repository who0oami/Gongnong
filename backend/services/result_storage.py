"""Persistent storage for rendered result videos."""

import os
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from boto3.exceptions import Boto3Error

from services.clip_resolver import create_s3_client


class ResultStorageUnavailable(RuntimeError):
    """A rendered result could not be stored or made available for playback."""


def _bucket_name() -> str:
    bucket = (os.getenv("S3_RESULT_BUCKET") or os.getenv("S3_CLIP_BUCKET") or "").strip()
    if not bucket:
        raise ResultStorageUnavailable("S3_RESULT_BUCKET 또는 S3_CLIP_BUCKET이 설정되지 않았습니다.")
    return bucket


def result_object_key(job_id: str) -> str:
    return f"results/{job_id}.mp4"


def upload_result_video(job_id: str, path: Path) -> str:
    if not path.is_file():
        raise ResultStorageUnavailable("렌더링 결과 파일을 찾을 수 없습니다.")
    try:
        client = create_s3_client()
        client.upload_file(
            str(path),
            _bucket_name(),
            result_object_key(job_id),
            ExtraArgs={"ContentType": "video/mp4"},
        )
    except (BotoCoreError, ClientError, Boto3Error, OSError) as exc:
        raise ResultStorageUnavailable(
            f"완성 영상을 S3에 저장하지 못했습니다: {type(exc).__name__}"
        ) from exc
    return f"/translate/jobs/{job_id}/video"


def create_result_download_url(job_id: str) -> str:
    try:
        expires = max(60, int(os.getenv("S3_RESULT_URL_EXPIRES_SECONDS", "3600")))
    except ValueError:
        expires = 3600
    try:
        client = create_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket_name(), "Key": result_object_key(job_id)},
            ExpiresIn=expires,
        )
    except (BotoCoreError, ClientError, Boto3Error, OSError) as exc:
        raise ResultStorageUnavailable(
            f"결과 영상 재생 주소를 생성하지 못했습니다: {type(exc).__name__}"
        ) from exc
