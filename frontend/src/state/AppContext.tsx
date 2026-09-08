import { createContext, useContext, useMemo, useReducer, type ReactNode } from "react";
import type {
  ConfirmDeleteState,
  Group,
  HistoryItem,
  OnboardingSelections,
  Profile,
  ScreenView,
  Settings,
} from "../types";

interface AppState {
  history: HistoryItem[];
  groups: Group[];
  settings: Settings;
  profile: Profile;
  onboarding: OnboardingSelections;
  currentUrl: string;
  confirmDelete: ConfirmDeleteState | null;
}

const INITIAL_HISTORY: HistoryItem[] = [
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

const initialState: AppState = {
  history: INITIAL_HISTORY,
  groups: [{ id: "g1", name: "수어 강의 모음", itemIds: ["2"] }],
  settings: { subtitles: true, autoSwitch: false, defaultSpeed: "1.0" },
  profile: { name: "공농 사용자", email: "user@gongnong.kr" },
  onboarding: { age: "", topics: [], prefs: [], view: "" },
  currentUrl: "",
  confirmDelete: null,
};

type Action =
  | { type: "ADD_HISTORY_ITEM"; item: HistoryItem }
  | { type: "REMOVE_HISTORY_ITEM"; id: string }
  | { type: "SET_HISTORY_STATUS"; id: string; status: HistoryItem["status"] }
  | { type: "ADD_GROUP"; group: Group }
  | { type: "REMOVE_GROUP"; id: string }
  | { type: "ADD_ITEM_TO_GROUP"; groupId: string; itemId: string }
  | { type: "REMOVE_ITEM_FROM_GROUP"; groupId: string; itemId: string }
  | { type: "SET_SETTINGS"; settings: Partial<Settings> }
  | { type: "SET_PROFILE"; profile: Partial<Profile> }
  | { type: "SET_ONBOARDING"; onboarding: Partial<OnboardingSelections> }
  | { type: "SET_CURRENT_URL"; url: string }
  | { type: "REQUEST_DELETE"; item: ConfirmDeleteState }
  | { type: "CANCEL_DELETE" }
  | { type: "CONFIRM_DELETE" };

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "ADD_HISTORY_ITEM":
      return { ...state, history: [action.item, ...state.history] };
    case "REMOVE_HISTORY_ITEM":
      return { ...state, history: state.history.filter((h) => h.id !== action.id) };
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
    case "SET_SETTINGS":
      return { ...state, settings: { ...state.settings, ...action.settings } };
    case "SET_PROFILE":
      return { ...state, profile: { ...state.profile, ...action.profile } };
    case "SET_ONBOARDING":
      return { ...state, onboarding: { ...state.onboarding, ...action.onboarding } };
    case "SET_CURRENT_URL":
      return { ...state, currentUrl: action.url };
    case "REQUEST_DELETE":
      return { ...state, confirmDelete: action.item };
    case "CANCEL_DELETE":
      return { ...state, confirmDelete: null };
    case "CONFIRM_DELETE":
      if (!state.confirmDelete) return state;
      return {
        ...state,
        history: state.history.filter((h) => h.id !== state.confirmDelete!.id),
        confirmDelete: null,
      };
    default:
      return state;
  }
}

interface AppContextValue extends AppState {
  addHistoryItem: (item: HistoryItem) => void;
  removeHistoryItem: (id: string) => void;
  addGroup: (group: Group) => void;
  removeGroup: (id: string) => void;
  addItemToGroup: (groupId: string, itemId: string) => void;
  removeItemFromGroup: (groupId: string, itemId: string) => void;
  setSettings: (settings: Partial<Settings>) => void;
  setProfile: (profile: Partial<Profile>) => void;
  setOnboarding: (onboarding: Partial<OnboardingSelections>) => void;
  toggleOnboardingTopic: (topic: string) => void;
  toggleOnboardingPref: (pref: string) => void;
  setScreenView: (view: ScreenView) => void;
  setCurrentUrl: (url: string) => void;
  requestDelete: (item: ConfirmDeleteState) => void;
  cancelDelete: () => void;
  confirmDeleteNow: () => void;
}

const AppCtx = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const value = useMemo<AppContextValue>(() => {
    return {
      ...state,
      addHistoryItem: (item) => dispatch({ type: "ADD_HISTORY_ITEM", item }),
      removeHistoryItem: (id) => dispatch({ type: "REMOVE_HISTORY_ITEM", id }),
      addGroup: (group) => dispatch({ type: "ADD_GROUP", group }),
      removeGroup: (id) => dispatch({ type: "REMOVE_GROUP", id }),
      addItemToGroup: (groupId, itemId) => dispatch({ type: "ADD_ITEM_TO_GROUP", groupId, itemId }),
      removeItemFromGroup: (groupId, itemId) => dispatch({ type: "REMOVE_ITEM_FROM_GROUP", groupId, itemId }),
      setSettings: (settings) => dispatch({ type: "SET_SETTINGS", settings }),
      setProfile: (profile) => dispatch({ type: "SET_PROFILE", profile }),
      setOnboarding: (onboarding) => dispatch({ type: "SET_ONBOARDING", onboarding }),
      toggleOnboardingTopic: (topic) => {
        const on = state.onboarding.topics.includes(topic);
        dispatch({
          type: "SET_ONBOARDING",
          onboarding: {
            topics: on ? state.onboarding.topics.filter((t) => t !== topic) : [...state.onboarding.topics, topic],
          },
        });
      },
      toggleOnboardingPref: (pref) => {
        const on = state.onboarding.prefs.includes(pref);
        dispatch({
          type: "SET_ONBOARDING",
          onboarding: {
            prefs: on
              ? state.onboarding.prefs.filter((p) => p !== pref)
              : [...state.onboarding.prefs, pref].slice(-2),
          },
        });
      },
      setScreenView: (view) => dispatch({ type: "SET_ONBOARDING", onboarding: { view } }),
      setCurrentUrl: (url) => dispatch({ type: "SET_CURRENT_URL", url }),
      requestDelete: (item) => dispatch({ type: "REQUEST_DELETE", item }),
      cancelDelete: () => dispatch({ type: "CANCEL_DELETE" }),
      confirmDeleteNow: () => dispatch({ type: "CONFIRM_DELETE" }),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

// Convenience: is the current screen mode "easy"?
export function useEasyMode(): boolean {
  const { onboarding } = useApp();
  return onboarding.view === "easy";
}
