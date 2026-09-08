export type HistoryStatus = "완료" | "실패" | "처리중";

export interface HistoryItem {
  id: string;
  title: string;
  url: string;
  date: string;
  status: HistoryStatus;
  duration: string;
}

export interface Group {
  id: string;
  name: string;
  itemIds: string[];
}

export interface Settings {
  subtitles: boolean;
  autoSwitch: boolean;
  defaultSpeed: string;
}

export type ScreenView = "" | "easy" | "standard";

export interface OnboardingSelections {
  age: string;
  topics: string[];
  prefs: string[];
  view: ScreenView;
}

export interface Profile {
  name: string;
  email: string;
}

export interface ConfirmDeleteState {
  id: string;
  title: string;
}
