import { useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useApp, useEasyMode } from "../state/AppContext";
import { thumbOf } from "../constants";
import gnWatch from "../assets/gn-watch.png";

const YT_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[\w-]+/;
const SAMPLE_URL = "https://www.youtube.com/watch?v=M7lc1UVf-VE";

export default function HomePage() {
  const easy = useEasyMode();
  return easy ? <EasyHome /> : <StandardHome />;
}

function useConvert() {
  const navigate = useNavigate();
  const { setCurrentUrl } = useApp();
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");

  function convert(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed) {
      setUrlError("유튜브 링크를 입력해주세요.");
      return;
    }
    if (!YT_REGEX.test(trimmed)) {
      setUrlError("올바른 유튜브 링크를 입력해주세요.");
      return;
    }
    setUrlError("");
    setCurrentUrl(trimmed);
    navigate("/processing");
  }

  return { url, setUrl, urlError, setUrlError, convert };
}

function EasyHome() {
  const { history } = useApp();
  const navigate = useNavigate();
  const { setCurrentUrl } = useApp();
  const { url, setUrl, urlError, convert } = useConvert();

  const done = history.filter((h) => h.status === "완료").slice(0, 3);

  function play(itemUrl: string) {
    setCurrentUrl(itemUrl);
    navigate("/player");
  }

  return (
    <div style={{ maxWidth: "720px", margin: "0 auto", width: "100%", padding: "32px 20px 64px", boxSizing: "border-box" }}>
      <h1 style={{ fontSize: "32px", fontWeight: 700, lineHeight: 1.4, margin: "0 0 12px" }}>
        영상 주소를
        <br />
        붙여넣어 주세요
      </h1>
      <p style={{ fontSize: "19px", color: "#5c655f", lineHeight: 1.6, margin: "0 0 24px" }}>주소를 넣으면 수어 영상을 만들어 드려요.</p>

      <input
        className="gn-input"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === "Enter") convert(url);
        }}
        placeholder="유튜브 주소 붙여넣기"
        style={{ width: "100%", boxSizing: "border-box", fontSize: "20px", padding: "22px 20px", border: "2px solid #C9E7D6", borderRadius: "16px", background: "#fff" }}
      />
      {urlError && (
        <p style={{ fontSize: "18px", color: "#DC2626", background: "#FEF2F2", borderRadius: "14px", padding: "14px 18px", margin: "14px 0 0" }}>
          {urlError}
        </p>
      )}
      <button
        onClick={() => convert(url)}
        className="hover-primary"
        style={{ width: "100%", marginTop: "14px", fontSize: "22px", fontWeight: 700, padding: "24px", background: "#10B45F", color: "#fff", border: "none", borderRadius: "16px", cursor: "pointer" }}
      >
        수어로 보기
      </button>
      <button
        onClick={() => setUrl(SAMPLE_URL)}
        className="hover-secondary"
        style={{ width: "100%", marginTop: "10px", fontSize: "18px", fontWeight: 600, padding: "20px", background: "#fff", color: "#0B7A4D", border: "2px solid #10B45F", borderRadius: "16px", cursor: "pointer" }}
      >
        예시 주소 넣어보기
      </button>

      {done.length > 0 && (
        <div style={{ marginTop: "40px" }}>
          <h2 style={{ fontSize: "24px", fontWeight: 700, margin: "0 0 16px" }}>최근에 본 영상</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {done.map((r) => (
              <div key={r.id} style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "18px", padding: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <div style={{ width: "132px", flexShrink: 0, aspectRatio: "16 / 9", borderRadius: "12px", overflow: "hidden", background: "#F0FAF5" }}>
                    <img src={thumbOf(r.url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                  </div>
                  <p style={{ flex: 1, minWidth: 0, fontSize: "19px", fontWeight: 600, lineHeight: 1.5, margin: 0 }}>{r.title}</p>
                </div>
                <button
                  onClick={() => play(r.url)}
                  className="hover-primary"
                  style={{ width: "100%", fontSize: "19px", fontWeight: 700, padding: "20px", background: "#10B45F", color: "#fff", border: "none", borderRadius: "14px", cursor: "pointer" }}
                >
                  다시 보기
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => navigate("/mypage")}
        className="hover-muted"
        style={{ width: "100%", marginTop: "32px", fontSize: "18px", fontWeight: 600, padding: "20px", background: "#fff", color: "#171C19", border: "1px solid #E5E8E7", borderRadius: "16px", cursor: "pointer" }}
      >
        내 설정 보기
      </button>
    </div>
  );
}

function StandardHome() {
  const { history, groups, setCurrentUrl } = useApp();
  const navigate = useNavigate();
  const { url, setUrl, urlError, convert } = useConvert();

  const done = history.filter((h) => h.status === "완료");
  const recent = done.slice(0, 4);

  function play(itemUrl: string) {
    setCurrentUrl(itemUrl);
    navigate("/player");
  }

  return (
    <div>
      <div style={{ padding: "64px 24px 80px", background: "linear-gradient(160deg, #F0FAF5 0%, #DDF5E8 60%, #f7fcf8 100%)" }}>
        <div style={{ maxWidth: "576px", margin: "0 auto", textAlign: "center" }}>
          <h1 style={{ fontSize: "30px", fontWeight: 700, margin: "0 0 8px" }}>유튜브 링크를 붙여넣으세요</h1>
          <p style={{ fontSize: "14px", color: "#747C78", margin: "0 0 24px" }}>AI가 자동으로 수어 통역 영상을 만들어드립니다</p>
          <div style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "16px", padding: "10px", display: "flex", gap: "8px", boxShadow: "0 4px 12px rgba(0,0,0,.06)" }}>
            <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: "8px", padding: "0 12px" }}>
              <svg viewBox="0 0 24 24" style={{ width: "20px", height: "20px", flexShrink: 0, fill: "#747C78" }}>
                <path d="M17 7h-4v2h4c1.65 0 3 1.35 3 3s-1.35 3-3 3h-4v2h4c2.76 0 5-2.24 5-5s-2.24-5-5-5zm-6 8H7c-1.65 0-3-1.35-3-3s1.35-3 3-3h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-2zm-3-4h8v2H8z" />
              </svg>
              <input
                className="gn-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e: KeyboardEvent) => {
                  if (e.key === "Enter") convert(url);
                }}
                placeholder="https://youtube.com/watch?v=..."
                style={{ flex: 1, minWidth: 0, border: "none", fontSize: "14px", padding: "10px 0", background: "transparent" }}
              />
            </div>
            <button
              onClick={() => convert(url)}
              className="hover-primary"
              style={{ background: "#10B45F", color: "#fff", padding: "12px 20px", border: "none", borderRadius: "12px", fontSize: "14px", fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" }}
            >
              수어로 보기
            </button>
          </div>
          {urlError && <p style={{ margin: "8px 0 0", fontSize: "14px", color: "#EF4444", textAlign: "left", padding: "0 4px" }}>{urlError}</p>}
          <button
            onClick={() => setUrl(SAMPLE_URL)}
            className="hover-green"
            style={{ marginTop: "12px", background: "none", border: "none", fontSize: "12px", color: "#747C78", textDecoration: "underline", textUnderlineOffset: "2px", cursor: "pointer" }}
          >
            샘플 링크 사용하기
          </button>
        </div>
      </div>

      <div style={{ maxWidth: "896px", margin: "0 auto", padding: "32px 16px" }}>
        {recent.length > 0 ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>최근 변환 기록</h2>
              <button onClick={() => navigate("/history")} style={{ background: "none", border: "none", fontSize: "14px", fontWeight: 500, color: "#10B45F", cursor: "pointer" }}>
                전체 보기
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "12px" }}>
              {recent.map((r) => (
                <button
                  key={r.id}
                  onClick={() => play(r.url)}
                  className="hover-card"
                  style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "16px", overflow: "hidden", padding: 0, cursor: "pointer", textAlign: "left", display: "flex", flexDirection: "column" }}
                >
                  <div style={{ position: "relative", aspectRatio: "16 / 9", background: "#F0FAF5" }}>
                    <img src={thumbOf(r.url)} alt={r.title} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                    <span style={{ position: "absolute", top: "8px", left: "8px", fontSize: "10px", fontWeight: 600, background: "#10B45F", color: "#fff", padding: "1px 6px", borderRadius: "999px" }}>
                      수어 지원
                    </span>
                  </div>
                  <div style={{ padding: "12px" }}>
                    <p style={{ fontSize: "12px", fontWeight: 600, margin: 0, lineHeight: 1.45 }}>{r.title}</p>
                    <p style={{ fontSize: "10px", color: "#747C78", margin: "4px 0 0" }}>
                      {r.date} · {r.duration}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px" }}>
              <img src={gnWatch} alt="" style={{ width: "88px", height: "auto" }} />
            </div>
            <p style={{ fontSize: "14px", fontWeight: 500, margin: 0 }}>아직 변환한 영상이 없어요</p>
            <p style={{ fontSize: "12px", color: "#747C78", margin: "4px 0 0" }}>위에서 유튜브 링크를 입력해보세요</p>
          </div>
        )}

        {groups.length > 0 && (
          <div style={{ marginTop: "32px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>내 그룹</h2>
              <button onClick={() => navigate("/history")} style={{ background: "none", border: "none", fontSize: "14px", fontWeight: 500, color: "#10B45F", cursor: "pointer" }}>
                관리
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "12px" }}>
              {groups.map((g) => {
                const gitems = history.filter((h) => g.itemIds.includes(h.id));
                return (
                  <button
                    key={g.id}
                    onClick={() => navigate("/history")}
                    className="hover-card"
                    style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "16px", padding: "16px", display: "flex", alignItems: "center", gap: "16px", cursor: "pointer", textAlign: "left" }}
                  >
                    <div style={{ position: "relative", width: "64px", height: "48px", flexShrink: 0 }}>
                      {gitems.slice(0, 3).map((h, i) => (
                        <div
                          key={h.id}
                          style={{
                            position: "absolute",
                            width: "44px",
                            height: "30px",
                            top: `${i * 5}px`,
                            left: `${i * 5}px`,
                            borderRadius: "8px",
                            overflow: "hidden",
                            border: "2px solid #fff",
                            boxShadow: "0 1px 2px rgba(0,0,0,.1)",
                            zIndex: 3 - i,
                          }}
                        >
                          <img src={thumbOf(h.url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                        </div>
                      ))}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px" }}>
                        <svg viewBox="0 0 24 24" style={{ width: "14px", height: "14px", fill: "#10B45F", flexShrink: 0 }}>
                          <path d="M10 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2h-8l-2-2z" />
                        </svg>
                        <p style={{ fontSize: "14px", fontWeight: 600, margin: 0 }}>{g.name}</p>
                      </div>
                      <p style={{ fontSize: "12px", color: "#747C78", margin: 0 }}>영상 {g.itemIds.length}개</p>
                    </div>
                    <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "#747C78", flexShrink: 0 }}>
                      <path d="M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
                    </svg>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
