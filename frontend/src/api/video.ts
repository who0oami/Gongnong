import { apiClient } from "./client";
import type { ConvertJob } from "../types";

export interface StartConvertRequest {
  sourceUrl: string;
}

// TODO: endpoint paths are placeholders pending the backend API spec. Whether job status is
// delivered via polling, SSE, or WebSocket is also undecided — getJobStatus below assumes simple
// polling (see the useConvertJob hook) and can be swapped out once that's settled. Also unconfirmed:
// - startConvert payload beyond sourceUrl (e.g. target layout/quality options)
// - ConvertJob field names/units returned by getJobStatus (see types/job.ts TODOs, incl. segments)
export const videoApi = {
  startConvert: (payload: StartConvertRequest) => apiClient.post<ConvertJob>("/videos/convert", payload),
  getJobStatus: (jobId: string) => apiClient.get<ConvertJob>(`/videos/convert/${jobId}`),
};
