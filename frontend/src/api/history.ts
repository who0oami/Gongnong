import { apiClient } from "./client";
import type { Group, HistoryItem } from "../types";

// TODO: endpoint paths are placeholders pending the backend API spec. Unconfirmed:
// - whether list()/listGroups() are paginated
// - HistoryItem field names returned by list() match types/domain.ts (esp. resultVideoUrl/subtitleUrl)
export const historyApi = {
  list: () => apiClient.get<HistoryItem[]>("/history"),
  remove: (id: string) => apiClient.delete<void>(`/history/${id}`),
  listGroups: () => apiClient.get<Group[]>("/history/groups"),
  createGroup: (name: string, itemIds: string[]) => apiClient.post<Group>("/history/groups", { name, itemIds }),
  removeGroup: (id: string) => apiClient.delete<void>(`/history/groups/${id}`),
  addItemToGroup: (groupId: string, itemId: string) =>
    apiClient.post<void>(`/history/groups/${groupId}/items`, { itemId }),
  removeItemFromGroup: (groupId: string, itemId: string) =>
    apiClient.delete<void>(`/history/groups/${groupId}/items/${itemId}`),
};
