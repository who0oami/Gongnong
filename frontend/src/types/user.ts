// TODO: extend with real fields once the backend user schema is confirmed (avatarUrl, role, createdAt, etc.)
// Per docs/api-field-requirements.md, MyPage's stats (총 변환 횟수/완료된 영상/총 시청 시간— currently
// computed client-side from the full history list in MyPage.tsx) may instead come from the backend
// as precomputed fields (totalConversions/completedVideos/totalWatchTimeSec) — confirm whether the
// backend computes these live or on a schedule, since that affects whether MyPage keeps computing
// them locally or just displays server values.
export interface User {
  id: string;
  email: string;
  name: string;
}
