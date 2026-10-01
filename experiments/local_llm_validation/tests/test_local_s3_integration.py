"""API + SQLite + real provider facade/CSV/renderer; external I/O is mocked."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import TranslationJob, TranscriptSegment, User
from routers import job
from services import llm_gloss_service as facade, clip_resolver, video_merger
from services.local_llm_gloss_service import LocalGlossConversionError, LocalGlossValidationError


class LocalS3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool,
                                    connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(User(id=1, name="Tester", username="tester", email="test@example.com", password_hash="unused"))
            db.commit()
        app = FastAPI()
        app.include_router(job.router)
        def get_test_db():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = get_test_db
        app.dependency_overrides[job.get_current_user_optional] = lambda: User(id=1)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.patch(job, "SessionLocal", self.sessions)
        self.patch(facade, "_PROVIDER", "local")
        self.patch(job, "DEMO_GLOSS_OVERRIDE", {})
        self.patch(job, "get_corrected_transcript_data", return_value={
            "transcript": "고민", "segments": [
                {"start": 0, "end": 2, "text": "고민", "corrected_text": "고민"}]})
        self.model = self.patch(facade, "convert_to_gloss_local", return_value=["고민", "미등록이름테스트"])
        self.download = self.patch(clip_resolver.boto3, "client").return_value.download_file
        self.download.side_effect = lambda bucket, key, path: Path(path).write_bytes(b"fixture")
        env = patch.dict("os.environ", S3_CLIP_BUCKET="ksl-tube-avatar-clips")
        env.start()
        self.addCleanup(env.stop)
        self.patch(job.subprocess, "run", return_value=Mock(stdout="1.0"))
        self.patch(video_merger, "RESULTS_DIR", Path(self.folder.name))
        self.normalize = self.patch(video_merger, "_normalize_clip", return_value=Path(self.folder.name)/"normalized.mp4")
        self.patch(video_merger, "_make_idle_pose", return_value=Path(self.folder.name)/"idle.mp4")
        self.patch(video_merger, "_concat", return_value=Path(self.folder.name)/"joined.mp4")
        self.overlay = self.patch(video_merger, "_overlay_caption", return_value=Path(self.folder.name)/"caption.mp4")

    def patch(self, target, name, *args, **kwargs):
        patcher = patch.object(target, name, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def run_job(self):
        response = self.client.post("/translate/jobs", json={"url": "https://youtu.be/R0TFP9TS6eA"})
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        response = self.client.get(f"/translate/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalars(select(TranslationJob)).one().user_id, 1)
            self.assertEqual(db.scalars(select(TranscriptSegment)).one().corrected_text, "고민")
        return response.json()

    def test_local_gloss_csv_download_mixed_caption_and_db_result(self):
        result = self.run_job()
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(result["result"]["video_url"].endswith(".mp4"))
        self.model.assert_called_once_with("고민")
        self.download.assert_called_once()
        self.assertEqual(self.download.call_args.args[:2], ("ksl-tube-avatar-clips", "clips/word/WORD0001.mp4"))
        self.normalize.assert_called_once()
        self.assertEqual(self.overlay.call_args.args[2], "미등록이름테스트")
        self.assertFalse(Path(self.download.call_args.args[2]).parent.exists())

    def test_validation_failure_recovers_as_caption_without_download(self):
        self.model.side_effect = LocalGlossValidationError("invalid meaning")
        self.assertEqual(self.run_job()["status"], "COMPLETED")
        self.download.assert_not_called()
        self.normalize.assert_not_called()
        self.assertEqual(self.overlay.call_args.args[2], "고민")

    def test_model_outage_fails_job_instead_of_hiding_as_caption(self):
        self.model.side_effect = LocalGlossConversionError("offline")
        result = self.run_job()
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_stage"], "KSL_CONVERTING")
        self.download.assert_not_called()
        self.overlay.assert_not_called()

    def test_s3_failure_keeps_text_in_result(self):
        from botocore.exceptions import NoCredentialsError
        self.download.side_effect = NoCredentialsError()
        self.assertEqual(self.run_job()["status"], "COMPLETED")
        self.normalize.assert_not_called()
        self.assertIn("고민", self.overlay.call_args.args[2])
