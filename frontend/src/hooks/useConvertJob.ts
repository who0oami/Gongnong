import { useCallback, useEffect, useRef, useState } from "react";
import { videoApi } from "../api/video";
import { ApiError } from "../api/client";
import type { ConvertJob } from "../types";

// Persisting the jobId (not the whole job) lets ProcessingPage recover in-flight jobs after a
// refresh by re-fetching status from the backend, per the "새로고침 후에도 상태 복구" requirement.
const JOB_ID_KEY = "gongnong_active_job_id";
// TODO: swap this interval-based polling for SSE/WebSocket once the backend confirms which
// transport it supports for job status updates — only this hook should need to change.
const POLL_INTERVAL_MS = 2000;

export function useConvertJob() {
  const [job, setJob] = useState<ConvertJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const stopPolling = useCallback(() => {
    window.clearInterval(pollRef.current);
    pollRef.current = undefined;
  }, []);

  const poll = useCallback(
    (jobId: string) => {
      stopPolling();
      pollRef.current = window.setInterval(async () => {
        try {
          const latest = await videoApi.getJobStatus(jobId);
          setJob(latest);
          if (latest.status === "COMPLETED" || latest.status === "FAILED") {
            stopPolling();
          }
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "상태 조회에 실패했습니다.");
          stopPolling();
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  const start = useCallback(
    async (sourceUrl: string) => {
      setError(null);
      try {
        const created = await videoApi.startConvert({ url: sourceUrl });
        setJob(created);
        sessionStorage.setItem(JOB_ID_KEY, created.job_id);
        poll(created.job_id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "변환 요청에 실패했습니다.");
      }
    },
    [poll],
  );

  // Called once on ProcessingPage mount; resumes an in-flight job from storage, if any, instead of
  // starting a duplicate one. Returns whether a job was actually resumed.
  const resume = useCallback(async () => {
    const jobId = sessionStorage.getItem(JOB_ID_KEY);
    if (!jobId) return false;
    try {
      const latest = await videoApi.getJobStatus(jobId);
      setJob(latest);
      if (latest.status !== "COMPLETED" && latest.status !== "FAILED") {
        poll(jobId);
      }
      return true;
    } catch {
      sessionStorage.removeItem(JOB_ID_KEY);
      return false;
    }
  }, [poll]);

  const clear = useCallback(() => {
    stopPolling();
    sessionStorage.removeItem(JOB_ID_KEY);
    setJob(null);
    setError(null);
  }, [stopPolling]);

  useEffect(() => stopPolling, [stopPolling]);

  return { job, error, start, resume, clear };
}
