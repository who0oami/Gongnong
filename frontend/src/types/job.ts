export type ConvertJobStatus = "pending" | "processing" | "completed" | "failed";

// One recognized sign-language unit within a completed job's result, timed against resultVideoUrl.
// TODO: confirm this shape with the backend team — field names (gloss vs label/token) and whether
// confidence is 0-1 or 0-100 are unconfirmed; PlayerPage's low-confidence banner (mocks/subtitles.ts)
// will read `confidence` once this is wired to a real job response.
export interface ConvertJobSegment {
  start: number; // seconds, relative to resultVideoUrl
  end: number;
  gloss: string;
  confidence: number;
}

// Shape of a video-to-sign-language conversion job.
// TODO: confirm field names, progress semantics, and subtitle delivery format (URL vs inline list) with the backend team.
export interface ConvertJob {
  jobId: string;
  sourceUrl: string;
  status: ConvertJobStatus;
  progress?: number; // 0-100
  resultVideoUrl?: string;
  subtitleUrl?: string;

  // TODO: backend segment structure will be aligned in a later task.
  segments?: ConvertJobSegment[];

  // Backend Job API does not currently expose timestamps.
  createdAt?: string;
  updatedAt?: string;

  // Backend failure information.
  failedStage?: string;
  errorCode?: string;
  errorMessage?: string;
}
