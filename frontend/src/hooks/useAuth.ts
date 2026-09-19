import { useCallback } from "react";
import { authApi, type LoginRequest, type SignupRequest } from "../api/auth";
import { ApiError } from "../api/client";
import { clearAuthToken, getAuthToken, setAuthToken } from "../api/tokenStorage";
import { useUser } from "../state/UserContext";
import type { ScreenView } from "../types";

// "데모 계정으로 시작하기" button credentials — logs into a real backend account, creating it on
// first use (see loginDemo below). Not a fake/local session; same account persists across visits.
const DEMO_LOGIN = { id: "est", password: "1234" };
const DEMO_SIGNUP = { name: "데모 사용자", id: "est", email: "est@demo.gongnong.local", password: "1234" };

// The only place that should call authApi and touch tokenStorage — pages/components should go
// through this hook instead of calling src/api/auth.ts directly, so token handling stays in one spot.
export function useAuth() {
  const { isAuthenticated, setAuthenticated, setProfile, setOnboardingCompleted, setSessionLoading, setScreenView } =
    useUser();

  const login = useCallback(
    async (payload: LoginRequest) => {
      const res = await authApi.login(payload);
      setAuthToken(res.accessToken);
      setProfile({ name: res.user.name, email: res.user.email });
      setOnboardingCompleted(res.user.onboardingCompleted);
      setScreenView(res.user.screenMode);
      setAuthenticated(true);
    },
    [setAuthenticated, setProfile, setOnboardingCompleted, setScreenView],
  );

  const signup = useCallback(
    async (payload: SignupRequest) => {
      const res = await authApi.signup(payload);
      setAuthToken(res.accessToken);
      setProfile({ name: res.user.name, email: res.user.email });
      setOnboardingCompleted(res.user.onboardingCompleted);
      setScreenView(res.user.screenMode);
      setAuthenticated(true);
    },
    [setAuthenticated, setProfile, setOnboardingCompleted, setScreenView],
  );

  // Logs into the shared demo account, creating it the first time it's ever used (401 means it
  // doesn't exist yet). Goes through the exact same login()/signup() success path as a real user.
  const loginDemo = useCallback(async () => {
    try {
      await login(DEMO_LOGIN);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        await signup(DEMO_SIGNUP);
      } else {
        throw err;
      }
    }
  }, [login, signup]);

  const logout = useCallback(() => {
    clearAuthToken();
    setAuthenticated(false);
  }, [setAuthenticated]);

  // Called once at app startup (see SessionBootstrap in App.tsx). A stored token is only ever an
  // optimistic guess (UserContext's initial isAuthenticated reads it directly) — this confirms it
  // still works against the backend and fills in the real profile, or drops it if it's stale.
  const restoreSession = useCallback(async () => {
    if (!getAuthToken()) {
      setSessionLoading(false);
      return;
    }
    try {
      const user = await authApi.me();
      setProfile({ name: user.name, email: user.email });
      setOnboardingCompleted(user.onboardingCompleted);
      setScreenView(user.screenMode);
      setAuthenticated(true);
    } catch {
      clearAuthToken();
      setAuthenticated(false);
    } finally {
      setSessionLoading(false);
    }
  }, [setAuthenticated, setProfile, setOnboardingCompleted, setSessionLoading, setScreenView]);

  // Called from OnboardingPage's final "공농 시작하기" step (with the screen mode chosen in step 4)
  // and from MyPage when the user changes their screen mode later — persists both onto the backend
  // so they survive a refresh/relogin. screenMode is optional: omit it to only flip
  // onboarding_completed, same as before this API accepted a body.
  const completeOnboarding = useCallback(
    async (screenMode?: ScreenView) => {
      const user = await authApi.completeOnboarding(screenMode);
      setOnboardingCompleted(user.onboardingCompleted);
      setScreenView(user.screenMode);
    },
    [setOnboardingCompleted, setScreenView],
  );

  return { isAuthenticated, login, loginDemo, signup, logout, restoreSession, completeOnboarding };
}
