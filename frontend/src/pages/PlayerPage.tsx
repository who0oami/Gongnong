import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp, useEasyMode } from "../state/AppContext";
import {
  ICON,
  LAYOUTS,
  LAYOUT_FLEX,
  LAYOUT_SHAPES,
  SPEEDS,
  SUBS,
  fmtTime,
  thumbOf,
  vidId,
  type LayoutId,
} from "../constants";

function deriveDefaultLayout(prefs: string[]): LayoutId {
  if (prefs.includes("원본 영상을 크게 보고 싶어요")) return "original-large";
  if (prefs.includes("수어를 크게 보고 싶어요")) return "sign-large";
  return "side-by-side";
}

export default function PlayerPage() {
  const navigate = useNavigate();
  const easy = useEasyMode();
  const { currentUrl, settings, onboarding } = useApp();

  const [layout, setLayout] = useState<LayoutId>(() => deriveDefaultLayout(onboarding.prefs));
  const [showLayout, setShowLayout] = useState(false);
  const [showConfDismissed, setShowConfDismissed] = useState(false);
  const [viewMode, setViewMode] = useState<"수어" | "자막">("수어");
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [speed, setSpeed] = useState(parseFloat(settings.defaultSpeed) || 1);
  const [speedOpen, setSpeedOpen] = useState(false);
  const duration = 180;

  useEffect(() => {
    if (!currentUrl) navigate("/home");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUrl]);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setTime((t) => {
        const nt = t + 0.5 * speed;
        if (nt >= duration) {
          setPlaying(false);
          return duration;
        }
        return nt;
      });
    }, 500);
    return () => window.clearInterval(id);
  }, [playing, speed, duration]);

  useEffect(() => {
    const sub = SUBS.find((s) => time >= s.start && time <= s.end);
    if (sub?.lowConf && settings.autoSwitch) setViewMode("자막");
  }, [time, settings.autoSwitch]);

  const sub = SUBS.find((s) => time >= s.start && time <= s.end);
  const showConf = !showConfDismissed && !!(sub && sub.lowConf);
  const showSubtitle = settings.subtitles && viewMode === "자막" && !!sub;
  const showOriginal = layout !== "sign-only";
  const showSign = layout !== "original-only";
  const layoutFlex = LAYOUT_FLEX[layout];
  const playerTitle = vidId(currentUrl) ? `YouTube · ${vidId(currentUrl)}` : currentUrl || "영상 없음";
  const watchUrl = vidId(currentUrl) ? `https://www.youtube.com/watch?v=${vidId(currentUrl)}` : "https://www.youtube.com";

  function backHome() {
    setPlaying(false);
    navigate("/home");
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setTime(Math.max(0, Math.min(duration, ((e.clientX - r.left) / r.width) * duration)));
  }

  const panelBase: React.CSSProperties = {
    position: "relative",
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "16px",
  };

  const barZoom = easy ? 1.5 : 1;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#0F1318" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "14px 20px", borderBottom: "1px solid rgba(255,255,255,.08)" }}>
        <button
          onClick={backHome}
          className="hover-white"
          style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", color: "rgba(255,255,255,.6)", background: "none", border: "none", cursor: "pointer", whiteSpace: "nowrap" }}
        >
          <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "currentColor" }}>
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
          </svg>
          뒤로
        </button>
        <p style={{ flex: 1, fontSize: "14px", fontWeight: 500, color: "rgba(255,255,255,.7)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>
          {playerTitle}
        </p>
      </div>

      {showLayout && (
        <div style={{ margin: "12px 16px 0", borderRadius: "16px", padding: "16px", background: "#1a1f2e", border: "1px solid rgba(255,255,255,.1)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <p style={{ fontSize: "14px", fontWeight: 700, color: "#fff", margin: 0 }}>레이아웃 선택</p>
            <button
              onClick={() => setShowLayout(false)}
              className="hover-white"
              style={{ background: "none", border: "none", color: "rgba(255,255,255,.4)", fontSize: "18px", lineHeight: 1, cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(88px, 1fr))", gap: "8px" }}>
            {LAYOUTS.map((l) => {
              const on = layout === l.id;
              const shapes = LAYOUT_SHAPES[l.id];
              const origFill = "#2d3748";
              const signFill = on ? "#8DDE98" : "#4a7c59";
              return (
                <button
                  key={l.id}
                  onClick={() => {
                    setLayout(l.id);
                    setShowLayout(false);
                  }}
                  style={{ display: "flex", flexDirection: "column", gap: "6px", background: "none", border: "none", padding: 0, cursor: "pointer" }}
                >
                  <div style={{ borderRadius: "12px", overflow: "hidden", outline: on ? "2px solid #10B45F" : "2px solid transparent", outlineOffset: "1px" }}>
                    <svg viewBox="0 0 56 36" style={{ width: "100%", display: "block", background: on ? "#10B45F" : "#1e2530", borderRadius: "8px" }}>
                      <rect x={shapes[0].x} y={shapes[0].y} width={shapes[0].w} height={shapes[0].h} rx={2} fill={origFill} />
                      <rect x={shapes[1].x} y={shapes[1].y} width={shapes[1].w} height={shapes[1].h} rx={2} fill={signFill} />
                    </svg>
                  </div>
                  <p style={{ fontSize: "10px", fontWeight: 600, textAlign: "center", lineHeight: 1.2, margin: 0, color: on ? "#10B45F" : "rgba(255,255,255,.5)" }}>{l.label}</p>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "16px", gap: "12px", position: "relative", minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: layout === "stacked" ? "column" : "row", gap: "12px", minHeight: 0 }}>
          {showOriginal && (
            <div style={{ ...panelBase, background: "#0a0c10", flex: layoutFlex[0], minHeight: "160px" }}>
              <img
                src={thumbOf(currentUrl, "maxresdefault")}
                alt="원본 영상"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.6 }}
              />
              <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,.5)" }} />
              <div style={{ position: "relative", zIndex: 10, textAlign: "center", padding: "0 24px" }}>
                <p style={{ color: "#fff", fontWeight: 600, fontSize: "14px", margin: "0 0 4px" }}>이 환경에서는 임베드가 제한됩니다</p>
                <p style={{ color: "rgba(255,255,255,.5)", fontSize: "12px", margin: "0 0 16px" }}>배포된 서비스 환경에서는 정상 재생됩니다</p>
                <a
                  href={watchUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: "8px", background: "#10B45F", color: "#fff", fontSize: "12px", fontWeight: 600, padding: "10px 16px", borderRadius: "12px", textDecoration: "none" }}
                >
                  <svg viewBox="0 0 24 24" style={{ width: "14px", height: "14px", fill: "#fff" }}>
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  YouTube에서 보기
                </a>
              </div>
              <div style={{ position: "absolute", top: "10px", left: "10px", fontSize: "10px", fontWeight: 600, color: "rgba(255,255,255,.5)", background: "rgba(0,0,0,.4)", padding: "1px 8px", borderRadius: "6px", zIndex: 10 }}>
                원본
              </div>
            </div>
          )}
          {showSign && (
            <div style={{ ...panelBase, background: "#111827", border: "1px solid rgba(255,255,255,.06)", flex: layoutFlex[1], minHeight: "120px" }}>
              <div style={{ textAlign: "center", padding: "0 12px" }}>
                <div style={{ width: "64px", height: "64px", borderRadius: "999px", margin: "0 auto 8px", background: "linear-gradient(135deg, #8DDE98, #1BAA70)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <svg viewBox="0 0 24 24" style={{ width: "32px", height: "32px", fill: "#fff" }}>
                    <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
                  </svg>
                </div>
                {playing ? (
                  <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-end", gap: "2px", height: "16px" }}>
                    {[5, 8, 12, 8, 5, 11, 6].map((h, i) => (
                      <span
                        key={i}
                        style={{
                          width: "2px",
                          height: `${h}px`,
                          borderRadius: "999px",
                          background: "#10B45F",
                          animation: `gn-bar .5s ease-in-out ${i * 0.1}s infinite alternate`,
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <p style={{ color: "rgba(255,255,255,.3)", fontSize: "12px", margin: 0 }}>재생 대기</p>
                )}
              </div>
              <div style={{ position: "absolute", top: "10px", left: "10px" }}>
                <span style={{ fontSize: "10px", fontWeight: 600, color: "rgba(255,255,255,.4)", background: "rgba(0,0,0,.3)", padding: "1px 8px", borderRadius: "6px" }}>수어</span>
              </div>
            </div>
          )}
        </div>

        {showConf && (
          <div style={{ position: "absolute", top: "8px", left: "8px", right: "8px", display: "flex", alignItems: "center", gap: "12px", padding: "10px 16px", borderRadius: "12px", background: "rgba(30,16,4,.85)", border: "1px solid rgba(249,115,22,.35)", backdropFilter: "blur(8px)", zIndex: 20 }}>
            <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "#fb923c", flexShrink: 0 }}>
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
            </svg>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: "14px", fontWeight: 600, color: "#fdba74", margin: 0 }}>정확하지 않을 수 있어요</p>
              <p style={{ fontSize: "12px", color: "rgba(251,146,60,.7)", margin: 0 }}>이 구간은 수어 변환 신뢰도가 낮습니다</p>
            </div>
            <button onClick={() => setViewMode("자막")} style={{ fontSize: "12px", background: "#f97316", color: "#fff", padding: "6px 12px", border: "none", borderRadius: "8px", fontWeight: 600, cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}>
              자막 보기
            </button>
            <button onClick={() => setShowConfDismissed(true)} style={{ background: "none", border: "none", color: "rgba(251,146,60,.5)", cursor: "pointer", flexShrink: 0, display: "flex" }}>
              <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "currentColor" }}>
                <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
              </svg>
            </button>
          </div>
        )}

        {showSubtitle && (
          <div style={{ position: "absolute", bottom: "12px", left: 0, right: 0, display: "flex", justifyContent: "center", pointerEvents: "none", zIndex: 20 }}>
            <p
              style={{
                fontSize: "16px",
                fontWeight: 600,
                padding: "12px 24px",
                borderRadius: "16px",
                textAlign: "center",
                maxWidth: "80%",
                margin: 0,
                lineHeight: 1.5,
                backdropFilter: "blur(6px)",
                boxShadow: "0 8px 24px rgba(0,0,0,.3)",
                background: sub && sub.lowConf ? "rgba(67,20,7,.9)" : "rgba(0,0,0,.75)",
                color: sub && sub.lowConf ? "#ffedd5" : "#fff",
                border: sub && sub.lowConf ? "1px solid rgba(249,115,22,.3)" : "none",
              }}
            >
              {sub ? sub.text : ""}
            </p>
          </div>
        )}
      </div>

      <div style={{ padding: "0 16px 16px" }}>
        <div style={{ borderRadius: "16px", padding: "16px", background: "rgba(255,255,255,.05)", border: "1px solid rgba(255,255,255,.08)", zoom: barZoom }}>
          <div style={{ marginBottom: "16px" }}>
            <div onClick={seek} style={{ position: "relative", height: "6px", background: "rgba(255,255,255,.12)", borderRadius: "999px", cursor: "pointer" }}>
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${(time / duration) * 100}%`, background: "#10B45F", borderRadius: "999px" }} />
              <div style={{ position: "absolute", top: "-3px", left: `${(time / duration) * 100}%`, width: "12px", height: "12px", marginLeft: "-6px", borderRadius: "999px", background: "#10B45F" }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "rgba(255,255,255,.35)", marginTop: "6px" }}>
              <span>{fmtTime(time)}</span>
              <span>{fmtTime(duration)}</span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "2px", borderRadius: "12px", padding: "4px", background: "rgba(255,255,255,.05)" }}>
              <button
                onClick={() => setViewMode("수어")}
                style={{ fontSize: "12px", fontWeight: 600, padding: "6px 12px", borderRadius: "8px", border: "none", cursor: "pointer", background: viewMode === "수어" ? "#10B45F" : "transparent", color: viewMode === "수어" ? "#fff" : "rgba(255,255,255,.4)" }}
              >
                수어
              </button>
              <button
                onClick={() => setViewMode("자막")}
                style={{ fontSize: "12px", fontWeight: 600, padding: "6px 12px", borderRadius: "8px", border: "none", cursor: "pointer", background: viewMode === "자막" ? "#10B45F" : "transparent", color: viewMode === "자막" ? "#fff" : "rgba(255,255,255,.4)" }}
              >
                자막
              </button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button onClick={() => setTime((t) => Math.max(0, t - 10))} className="hover-white" style={{ background: "none", border: "none", color: "rgba(255,255,255,.5)", cursor: "pointer", display: "flex" }}>
                <svg viewBox="0 0 24 24" style={{ width: "20px", height: "20px", fill: "currentColor" }}>
                  <path d="M11 18V6l-8.5 6 8.5 6zm.5-6 8.5 6V6l-8.5 6z" />
                </svg>
              </button>
              <button
                onClick={() => setPlaying((p) => !p)}
                style={{ width: "44px", height: "44px", borderRadius: "999px", background: "#10B45F", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <svg viewBox="0 0 24 24" style={{ width: "20px", height: "20px", fill: "#fff" }}>
                  <path d={playing ? ICON.pause : ICON.play} />
                </svg>
              </button>
              <button onClick={() => setTime((t) => Math.min(duration, t + 10))} className="hover-white" style={{ background: "none", border: "none", color: "rgba(255,255,255,.5)", cursor: "pointer", display: "flex" }}>
                <svg viewBox="0 0 24 24" style={{ width: "20px", height: "20px", fill: "currentColor" }}>
                  <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z" />
                </svg>
              </button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div style={{ position: "relative" }}>
                <button
                  onClick={() => setSpeedOpen((o) => !o)}
                  style={{ fontSize: "12px", fontWeight: 600, padding: "8px 12px", borderRadius: "12px", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", whiteSpace: "nowrap", background: speedOpen ? "#10B45F" : "rgba(255,255,255,.07)", color: speedOpen ? "#fff" : "rgba(255,255,255,.5)" }}
                >
                  {speed === 1 ? "배속" : `${speed}x`}
                  <svg viewBox="0 0 24 24" style={{ width: "12px", height: "12px", fill: "currentColor", transform: speedOpen ? "rotate(180deg)" : "none" }}>
                    <path d="M7 10l5 5 5-5z" />
                  </svg>
                </button>
                {speedOpen && (
                  <div style={{ position: "absolute", bottom: "100%", marginBottom: "8px", right: 0, borderRadius: "12px", overflow: "hidden", padding: "4px 0", background: "#1e2530", border: "1px solid rgba(255,255,255,.1)", minWidth: "96px", zIndex: 30 }}>
                    {SPEEDS.map((v) => (
                      <button
                        key={v}
                        onClick={() => {
                          setSpeed(v);
                          setSpeedOpen(false);
                        }}
                        style={{ width: "100%", textAlign: "center", fontSize: "12px", padding: "8px 16px", border: "none", cursor: "pointer", color: speed === v ? "#10B45F" : "rgba(255,255,255,.6)", background: speed === v ? "rgba(16,180,95,.1)" : "transparent", fontWeight: speed === v ? 700 : 400 }}
                      >
                        {v === 1 ? "1x (기본)" : `${v}x`}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => setShowLayout((s) => !s)}
                style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, padding: "8px 12px", borderRadius: "12px", border: "none", cursor: "pointer", whiteSpace: "nowrap", background: showLayout ? "#10B45F" : "rgba(255,255,255,.07)", color: showLayout ? "#fff" : "rgba(255,255,255,.5)" }}
              >
                <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "currentColor" }}>
                  <path d="M3 5v4h2V5h4V3H5C3.9 3 3 3.9 3 5zm2 10H3v4c0 1.1.9 2 2 2h4v-2H5v-4zm14 4h-4v2h4c1.1 0 2-.9 2-2v-4h-2v4zm0-16h-4v2h4v4h2V5c0-1.1-.9-2-2-2z" />
                </svg>
                레이아웃
              </button>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "rgba(255,255,255,.3)", whiteSpace: "nowrap" }}>
                <span style={{ width: "6px", height: "6px", background: "#10B45F", borderRadius: "999px" }} />
                동기화됨
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
