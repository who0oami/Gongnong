import type { CSSProperties, RefObject } from "react";
import type { LayoutId } from "../../../constants";
import { thumbOf } from "../../../utils/video";

const panelBase: CSSProperties = {
  position: "relative",
  overflow: "hidden",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "16px",
};

interface VideoStageProps {
  layout: LayoutId;
  showOriginal: boolean;
  showSign: boolean;
  layoutFlex: [number, number];
  currentUrl: string;
  watchUrl: string;
  hasRealVideo: boolean;
  resultVideoUrl?: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  playing: boolean;
  onTimeUpdate: () => void;
  onLoadedMetadata: () => void;
  onPlay: () => void;
  onPause: () => void;
  onEnded: () => void;
}

export default function VideoStage({
  layout,
  showOriginal,
  showSign,
  layoutFlex,
  currentUrl,
  watchUrl,
  hasRealVideo,
  resultVideoUrl,
  videoRef,
  playing,
  onTimeUpdate,
  onLoadedMetadata,
  onPlay,
  onPause,
  onEnded,
}: VideoStageProps) {
  return (
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
          {hasRealVideo ? (
            <video
              ref={videoRef}
              src={resultVideoUrl}
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
              onTimeUpdate={onTimeUpdate}
              onLoadedMetadata={onLoadedMetadata}
              onPlay={onPlay}
              onPause={onPause}
              onEnded={onEnded}
            />
          ) : (
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
          )}
          <div style={{ position: "absolute", top: "10px", left: "10px" }}>
            <span style={{ fontSize: "10px", fontWeight: 600, color: "rgba(255,255,255,.4)", background: "rgba(0,0,0,.3)", padding: "1px 8px", borderRadius: "6px" }}>수어</span>
          </div>
        </div>
      )}
    </div>
  );
}
