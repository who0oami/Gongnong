export function vidId(u: string): string | null {
  const m = (u || "").match(/(?:v=|youtu\.be\/)([^&?/]+)/);
  return m ? m[1] : null;
}

export function thumbOf(u: string, q?: string): string {
  const v = vidId(u);
  return v ? `https://img.youtube.com/vi/${v}/${q || "mqdefault"}.jpg` : "";
}

export function parseDur(d: string): number {
  const p = (d || "").split(":").map(Number);
  return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p.length === 2 ? p[0] * 60 + p[1] : 0;
}

export function fmtWatch(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function fmtTime(n: number): string {
  return Math.floor(n / 60) + ":" + String(Math.floor(n % 60)).padStart(2, "0");
}
