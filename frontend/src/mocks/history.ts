import type { Group, HistoryItem } from "../types";

// No backend History API yet — every account (including the demo account) starts with an empty
// history until GET /api/history exists. TODO: replace with real data once it's connected.
export const MOCK_HISTORY: HistoryItem[] = [];

// TODO: replace with real data from GET /api/history/groups once the backend is connected.
export const MOCK_GROUPS: Group[] = [];
