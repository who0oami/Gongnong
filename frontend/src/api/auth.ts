import { apiClient } from "./client";
import type { User } from "../types";

export interface LoginRequest {
  id: string;
  password: string;
}

export interface SignupRequest {
  name: string;
  id: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  accessToken: string;
}

// TODO: none of these paths/payloads are confirmed with the backend yet — treat them as a
// placeholder shape to wire real endpoints into once the API spec exists. Unconfirmed:
// - endpoint paths themselves (/auth/*)
// - login/signup identifier field: `id` vs `username`/`email`
// - AuthResponse envelope: bare {user, accessToken} vs wrapped (see types/api.ts ApiResponse<T>)
//
// 백엔드 확정: 세션은 JWT 방식, access_token만 발급 (MVP에서는 refreshToken 생략). AuthResponse의
// accessToken이 이 JWT access_token에 해당하며, 만료 시 별도 갱신 없이 재로그인이 필요하다.
export const authApi = {
  login: (payload: LoginRequest) => apiClient.post<AuthResponse>("/auth/login", payload),
  signup: (payload: SignupRequest) => apiClient.post<AuthResponse>("/auth/signup", payload),
  logout: () => apiClient.post<void>("/auth/logout"),
  findId: (email: string) => apiClient.post<{ id: string }>("/auth/find-id", { email }),
  findPassword: (id: string, email: string) => apiClient.post<void>("/auth/find-password", { id, email }),
};
