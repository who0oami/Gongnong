import type { Group, HistoryItem } from "../types";

// TODO: replace with real data from GET /api/history once the backend is connected.
export const MOCK_HISTORY: HistoryItem[] = [
  {
    id: "1",
    title: "2024 국제 농아인 수어 공연 하이라이트",
    url: "https://www.youtube.com/watch?v=M7lc1UVf-VE",
    date: "2026-09-03",
    status: "완료",
    duration: "5:24",
  },
  {
    id: "2",
    title: "한국수어 기초 강의 - 인사말과 자기소개",
    url: "https://www.youtube.com/watch?v=oHg5SJYRHA0",
    date: "2026-09-01",
    status: "완료",
    duration: "12:08",
  },
  {
    id: "3",
    title: "뉴스 9시 - 장애인 접근성 정책 발표",
    url: "https://www.youtube.com/watch?v=abc123",
    date: "2026-08-30",
    status: "실패",
    duration: "3:15",
  },
];

// TODO: replace with real data from GET /api/history/groups once the backend is connected.
export const MOCK_GROUPS: Group[] = [{ id: "g1", name: "수어 강의 모음", itemIds: ["2"] }];
