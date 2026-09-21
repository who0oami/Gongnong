import { apiClient } from "./client";
import type { ConvertJob } from "../types";

export interface StartConvertRequest {
  sourceUrl: string;
}

type BackendJobStatus =
  | "QUEUED"
  | "TRANSCRIPTING"
  | "KSL_CONVERTING"
  | "SIGN_MAPPING"
  | "TIMELINE_BUILDING"
  | "COMPLETED"
  | "FAILED";

interface BackendJobResult {
  video_url?: string | null;
}

interface BackendJobResponse {
  job_id: string;
  status: BackendJobStatus;
  url: string;
  result?: BackendJobResult | null;
  failed_stage?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

function mapJobStatus(status: BackendJobStatus): ConvertJob["status"] {
  switch (status) {
    case "QUEUED":
      return "pending";

    case "TRANSCRIPTING":
    case "KSL_CONVERTING":
    case "SIGN_MAPPING":
    case "TIMELINE_BUILDING":
      return "processing";

    case "COMPLETED":
      return "completed";

    case "FAILED":
      return "failed";
  }
}

function mapBackendJob(job: BackendJobResponse): ConvertJob {
  return {
    jobId: job.job_id,
    sourceUrl: job.url,
    status: mapJobStatus(job.status),
    resultVideoUrl: job.result?.video_url ?? undefined,
    failedStage: job.failed_stage ?? undefined,
    errorCode: job.error_code ?? undefined,
    errorMessage: job.error_message ?? undefined,
  };
}

export const videoApi = {
  startConvert: async (payload: StartConvertRequest): Promise<ConvertJob> => {
    const job = await apiClient.post<BackendJobResponse>("/translate/jobs", {
      url: payload.sourceUrl,
    });

    return mapBackendJob(job);
  },

  getJobStatus: async (jobId: string): Promise<ConvertJob> => {
    const job = await apiClient.get<BackendJobResponse>(
      `/translate/jobs/${jobId}`,
    );

    return mapBackendJob(job);
  },
};
