import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from youtube_transcript_api._errors import RequestBlocked

from routers import job
from services import gemini_transcript_service as gemini_transcript
from services import subtitle_pipeline_service as pipeline
from services import youtube_service


class TranscriptFallbackTests(unittest.TestCase):
    def test_cloud_ip_block_uses_gemini_transcript_and_skips_second_correction(self):
        fallback_segments = [
            {"start": 0.0, "end": 2.0, "text": "첫 문장"},
            {"start": 2.0, "end": 4.0, "text": "둘째 문장"},
        ]
        with patch.object(pipeline, "extract_video_id", return_value="video-id"), \
                patch.object(pipeline, "get_video_metadata", return_value={"title": "", "description": ""}), \
                patch.object(
                    pipeline,
                    "get_transcript_data",
                    side_effect=youtube_service.TranscriptAccessBlocked("blocked"),
                ), \
                patch.object(
                    pipeline,
                    "transcribe_youtube_video",
                    return_value=("첫 문장 둘째 문장", fallback_segments),
                ) as fallback, \
                patch.object(pipeline, "correct_segments") as correct:
            result = pipeline.get_corrected_transcript_data("https://youtu.be/video-id")

        fallback.assert_called_once_with("https://youtu.be/video-id")
        correct.assert_not_called()
        self.assertEqual(result["transcript"], "첫 문장 둘째 문장")
        self.assertEqual(
            result["segments"],
            [{**segment, "corrected_text": segment["text"]} for segment in fallback_segments],
        )

    def test_youtube_block_is_exposed_as_specific_value_error(self):
        with patch.object(youtube_service, "YouTubeTranscriptApi") as api:
            api.return_value.fetch.side_effect = RequestBlocked("video-id")
            with self.assertRaises(youtube_service.TranscriptAccessBlocked):
                youtube_service.get_transcript_data("video-id")

    def test_gemini_transcript_validates_and_sorts_segments(self):
        response = Mock()
        response.text = json.dumps({
            "segments": [
                {"start": 3, "end": 5, "text": " 둘째 "},
                {"start": 0, "end": 2, "text": "첫째"},
                {"start": 6, "end": 6, "text": "invalid"},
            ]
        })
        with patch.object(gemini_transcript, "generate_content", return_value=response) as generate:
            transcript, segments = gemini_transcript.transcribe_youtube_video(
                "https://www.youtube.com/watch?v=video-id"
            )

        self.assertEqual(transcript, "첫째 둘째")
        self.assertEqual(segments, [
            {"start": 0.0, "end": 2.0, "text": "첫째"},
            {"start": 3.0, "end": 5.0, "text": "둘째"},
        ])
        self.assertEqual(generate.call_count, 1)

    def test_unexpected_transcript_error_marks_job_failed(self):
        with patch.object(job, "SessionLocal") as session, \
                patch.object(job, "extract_video_id", return_value="video-id"), \
                patch.object(
                    job,
                    "get_corrected_transcript_data",
                    side_effect=RuntimeError("private failure"),
                ), \
                patch.object(job, "job_repository") as repository, \
                patch.object(job.logger, "exception"):
            asyncio.run(job.process_job("job-id", "https://youtu.be/video-id"))

        failure = repository.update_translation_job_db.call_args.kwargs
        self.assertEqual(failure["status"], job.JobStatus.FAILED)
        self.assertEqual(failure["failed_stage"], "TRANSCRIPTING")
        self.assertEqual(failure["error_code"], "TRANSCRIPT_INTERNAL_ERROR")
        self.assertNotIn("private failure", failure["error_message"])
        session.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
