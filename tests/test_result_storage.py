import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from routers import job
from services import result_storage


class ResultStorageTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "S3_CLIP_BUCKET": "clip-bucket",
            "S3_RESULT_BUCKET": "result-bucket",
            "S3_RESULT_URL_EXPIRES_SECONDS": "900",
        })
        env.start()
        self.addCleanup(env.stop)
        factory = patch.object(result_storage, "create_s3_client")
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = self.factory.return_value

    def test_upload_uses_persistent_key_and_returns_backend_playback_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job-id.mp4"
            path.write_bytes(b"video")
            url = result_storage.upload_result_video("job-id", path)
        self.assertEqual(url, "/translate/jobs/job-id/video")
        self.client.upload_file.assert_called_once_with(
            str(path), "result-bucket", "results/job-id.mp4",
            ExtraArgs={"ContentType": "video/mp4"},
        )

    def test_clip_bucket_is_result_bucket_fallback(self):
        with patch.dict(os.environ, {"S3_RESULT_BUCKET": ""}), tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job-id.mp4"
            path.write_bytes(b"video")
            result_storage.upload_result_video("job-id", path)
        self.assertEqual(self.client.upload_file.call_args.args[1], "clip-bucket")

    def test_upload_failure_is_explicit(self):
        self.client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "PutObject",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job-id.mp4"
            path.write_bytes(b"video")
            with self.assertRaises(result_storage.ResultStorageUnavailable):
                result_storage.upload_result_video("job-id", path)

    def test_presigned_url_is_created_on_each_playback_request(self):
        self.client.generate_presigned_url.return_value = "https://signed.example/video"
        self.assertEqual(
            result_storage.create_result_download_url("job-id"),
            "https://signed.example/video",
        )
        self.client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "result-bucket", "Key": "results/job-id.mp4"},
            ExpiresIn=900,
        )

    def test_local_result_is_removed_after_successful_upload(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(job, "RESULTS_DIR", Path(directory)), \
                patch.object(job, "upload_result_video", return_value="/translate/jobs/job-id/video") as upload:
            path = Path(directory) / "job-id.mp4"
            path.write_bytes(b"video")
            result = job._persist_result_video("job-id", "/static/results/job-id.mp4")
            self.assertFalse(path.exists())
        self.assertEqual(result, "/translate/jobs/job-id/video")
        upload.assert_called_once_with("job-id", path)

    def test_playback_endpoint_redirects_only_completed_jobs(self):
        completed = Mock(status=job.JobStatus.COMPLETED.value, result_video_url="/translate/jobs/job-id/video")
        with patch.object(job.job_repository, "get_translation_job_with_video_db", return_value=(completed, Mock())), \
                patch.object(job, "create_result_download_url", return_value="https://signed.example/video"):
            response = asyncio.run(job.play_translation_result("job-id", db=Mock()))
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "https://signed.example/video")


if __name__ == "__main__":
    unittest.main()
