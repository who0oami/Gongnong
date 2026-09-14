import { createContext, useContext, useMemo, useReducer, type ReactNode } from "react";
import type { ConfirmDeleteState, ConvertJob, Group, HistoryItem } from "../types";
import { MOCK_GROUPS, MOCK_HISTORY } from "../mocks/history";

interface VideoState {
  history: HistoryItem[];
  groups: Group[];
  currentUrl: string;
  confirmDelete: ConfirmDeleteState | null;
  // The most recently completed conversion job, set by ProcessingPage and read by PlayerPage so a
  // freshly-converted video's resultVideoUrl/subtitleUrl are available without a re-fetch. Replaying
  // an older item from HistoryPage instead goes through the matching HistoryItem's own fields.
  currentJob: ConvertJob | null;
}

// TODO: replace with real data from src/api/history.ts once the backend is connected.
const initialState: VideoState = {
  history: MOCK_HISTORY,
  groups: MOCK_GROUPS,
  currentUrl: "",
  confirmDelete: null,
  currentJob: null,
};

type Action =
  | { type: "ADD_HISTORY_ITEM"; item: HistoryItem }
  | { type: "REMOVE_HISTORY_ITEM"; id: string }
  | { type: "SET_HISTORY_STATUS"; id: string; status: HistoryItem["status"] }
  | { type: "ADD_GROUP"; group: Group }
  | { type: "REMOVE_GROUP"; id: string }
  | { type: "ADD_ITEM_TO_GROUP"; groupId: string; itemId: string }
  | { type: "REMOVE_ITEM_FROM_GROUP"; groupId: string; itemId: string }
  | { type: "SET_CURRENT_URL"; url: string }
  | { type: "SET_CURRENT_JOB"; job: ConvertJob | null }
  | { type: "REQUEST_DELETE"; item: ConfirmDeleteState }
  | { type: "CANCEL_DELETE" }
  | { type: "CONFIRM_DELETE" };

function reducer(state: VideoState, action: Action): VideoState {
  switch (action.type) {
    case "ADD_HISTORY_ITEM":
      return { ...state, history: [action.item, ...state.history] };
    case "REMOVE_HISTORY_ITEM":
      return {
        ...state,
        history: state.history.filter((h) => h.id !== action.id),
        groups: state.groups.map((g) => ({ ...g, itemIds: g.itemIds.filter((id) => id !== action.id) })),
      };
    case "SET_HISTORY_STATUS":
      return {
        ...state,
        history: state.history.map((h) => (h.id === action.id ? { ...h, status: action.status } : h)),
      };
    case "ADD_GROUP":
      return { ...state, groups: [...state.groups, action.group] };
    case "REMOVE_GROUP":
      return { ...state, groups: state.groups.filter((g) => g.id !== action.id) };
    case "ADD_ITEM_TO_GROUP":
      return {
        ...state,
        groups: state.groups.map((g) =>
          g.id === action.groupId && !g.itemIds.includes(action.itemId)
            ? { ...g, itemIds: [...g.itemIds, action.itemId] }
            : g,
        ),
      };
    case "REMOVE_ITEM_FROM_GROUP":
      return {
        ...state,
        groups: state.groups.map((g) =>
          g.id === action.groupId ? { ...g, itemIds: g.itemIds.filter((id) => id !== action.itemId) } : g,
        ),
      };
    case "SET_CURRENT_URL":
      return { ...state, currentUrl: action.url };
    case "SET_CURRENT_JOB":
      return { ...state, currentJob: action.job };
    case "REQUEST_DELETE":
      return { ...state, confirmDelete: action.item };
    case "CANCEL_DELETE":
      return { ...state, confirmDelete: null };
    case "CONFIRM_DELETE": {
      if (!state.confirmDelete) return state;
      const deletedId = state.confirmDelete.id;
      return {
        ...state,
        history: state.history.filter((h) => h.id !== deletedId),
        groups: state.groups.map((g) => ({ ...g, itemIds: g.itemIds.filter((id) => id !== deletedId) })),
        confirmDelete: null,
      };
    }
    default:
      return state;
  }
}

interface VideoContextValue extends VideoState {
  addHistoryItem: (item: HistoryItem) => void;
  removeHistoryItem: (id: string) => void;
  addGroup: (group: Group) => void;
  removeGroup: (id: string) => void;
  addItemToGroup: (groupId: string, itemId: string) => void;
  removeItemFromGroup: (groupId: string, itemId: string) => void;
  setCurrentUrl: (url: string) => void;
  setCurrentJob: (job: ConvertJob | null) => void;
  requestDelete: (item: ConfirmDeleteState) => void;
  cancelDelete: () => void;
  confirmDeleteNow: () => void;
}

const VideoCtx = createContext<VideoContextValue | null>(null);

export function VideoProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const value = useMemo<VideoContextValue>(() => {
    return {
      ...state,
      addHistoryItem: (item) => dispatch({ type: "ADD_HISTORY_ITEM", item }),
      removeHistoryItem: (id) => dispatch({ type: "REMOVE_HISTORY_ITEM", id }),
      addGroup: (group) => dispatch({ type: "ADD_GROUP", group }),
      removeGroup: (id) => dispatch({ type: "REMOVE_GROUP", id }),
      addItemToGroup: (groupId, itemId) => dispatch({ type: "ADD_ITEM_TO_GROUP", groupId, itemId }),
      removeItemFromGroup: (groupId, itemId) => dispatch({ type: "REMOVE_ITEM_FROM_GROUP", groupId, itemId }),
      setCurrentUrl: (url) => dispatch({ type: "SET_CURRENT_URL", url }),
      setCurrentJob: (job) => dispatch({ type: "SET_CURRENT_JOB", job }),
      requestDelete: (item) => dispatch({ type: "REQUEST_DELETE", item }),
      cancelDelete: () => dispatch({ type: "CANCEL_DELETE" }),
      confirmDeleteNow: () => dispatch({ type: "CONFIRM_DELETE" }),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  return <VideoCtx.Provider value={value}>{children}</VideoCtx.Provider>;
}

export function useVideo(): VideoContextValue {
  const ctx = useContext(VideoCtx);
  if (!ctx) throw new Error("useVideo must be used within VideoProvider");
  return ctx;
}
