import { createContext, useContext, useMemo, useReducer, type ReactNode } from "react";
import type { OnboardingSelections, Profile, ScreenView, Settings } from "../types";
import { getAuthToken } from "../api/tokenStorage";

interface UserState {
  profile: Profile;
  settings: Settings;
  onboarding: OnboardingSelections;
  // Set from a stored token at startup and from login/logout afterwards — see src/hooks/useAuth.ts,
  // which is the only place that should call authApi and touch tokenStorage.
  isAuthenticated: boolean;
}

// TODO: replace profile/settings defaults with the real GET /api/user response once the backend is connected.
const initialState: UserState = {
  profile: { name: "공농 사용자", email: "user@gongnong.kr" },
  settings: { subtitles: true, autoSwitch: false, defaultSpeed: "1.0" },
  onboarding: { age: "", topics: [], prefs: [], view: "" },
  isAuthenticated: getAuthToken() !== null,
};

type Action =
  | { type: "SET_SETTINGS"; settings: Partial<Settings> }
  | { type: "SET_PROFILE"; profile: Partial<Profile> }
  | { type: "SET_ONBOARDING"; onboarding: Partial<OnboardingSelections> }
  | { type: "SET_AUTHENTICATED"; value: boolean };

function reducer(state: UserState, action: Action): UserState {
  switch (action.type) {
    case "SET_SETTINGS":
      return { ...state, settings: { ...state.settings, ...action.settings } };
    case "SET_PROFILE":
      return { ...state, profile: { ...state.profile, ...action.profile } };
    case "SET_ONBOARDING":
      return { ...state, onboarding: { ...state.onboarding, ...action.onboarding } };
    case "SET_AUTHENTICATED":
      return { ...state, isAuthenticated: action.value };
    default:
      return state;
  }
}

interface UserContextValue extends UserState {
  setSettings: (settings: Partial<Settings>) => void;
  setProfile: (profile: Partial<Profile>) => void;
  setOnboarding: (onboarding: Partial<OnboardingSelections>) => void;
  toggleOnboardingTopic: (topic: string) => void;
  toggleOnboardingPref: (pref: string) => void;
  setScreenView: (view: ScreenView) => void;
  setAuthenticated: (value: boolean) => void;
}

const UserCtx = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const value = useMemo<UserContextValue>(() => {
    return {
      ...state,
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
      setAuthenticated: (value) => dispatch({ type: "SET_AUTHENTICATED", value }),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  return <UserCtx.Provider value={value}>{children}</UserCtx.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserCtx);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
