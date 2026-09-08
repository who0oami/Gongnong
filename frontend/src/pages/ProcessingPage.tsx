import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../state/AppContext";
import { PROC_STEPS, TOTAL, thumbOf, vidId } from "../constants";
import logo from "../assets/logo.png";

export default function ProcessingPage() {
  const navigate = useNavigate();
  const { currentUrl, addHistoryItem } = useApp();
  const [progress, setProgress] = useState(0);
  const [procStep, setProcStep] = useState(0);
  const doneRef = useRef(false);

  useEffect(() => {
    if (!currentUrl) {
      navigate("/home");
      return;
    }
    doneRef.current = false;
    let elapsed = 0;
    const interval = window.setInterval(() => {
      elapsed += 100;
      let step = 0;
      let acc = 0;
      for (let i = 0; i < PROC_STEPS.length; i++) {
        acc += PROC_STEPS[i].duration;
        if (elapsed < acc) {
          step = i;
          break;
        }
        step = i;
      }
      setProgress(Math.min(Math.round((elapsed / TOTAL) * 100), 99));
      setProcStep(step);
      if (elapsed >= TOTAL && !doneRef.current) {
        doneRef.current = true;
        window.clearInterval(interval);
        setProgress(100);
        window.setTimeout(() => {
          const v = vidId(currentUrl);
          addHistoryItem({
            id: String(Date.now()),
            title: v ? `YouTube 영상 (${v})` : "유튜브 영상",
            url: currentUrl,
            date: new Date().toISOString().slice(0, 10),
            status: "완료",
            duration: "3:42",
          });
          navigate("/player");
        }, 500);
      }
    }, 100);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUrl]);

  const etaLabel =
    progress < 100
      ? `완료까지 약 ${Math.max(0, Math.ceil(((100 - progress) / 100) * (TOTAL / 1000)))}초 남았습니다`
      : "변환이 완료되었습니다!";

  return (
    <div style={{ minHeight: "100vh", background: "#F0FAF5", display: "flex", flexDirection: "column" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #E5E8E7", height: "64px", display: "flex", alignItems: "center", padding: "0 24px" }}>
        <img src={logo} alt="공농" style={{ height: "34px", width: "auto" }} />
      </header>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 16px" }}>
        <div style={{ width: "100%", maxWidth: "448px" }}>
          <div style={{ textAlign: "center", marginBottom: "16px" }}>
            <p style={{ fontSize: "24px", fontWeight: 700, margin: 0 }}>수어 영상을 생성하고 있어요</p>
            <p style={{ fontSize: "14px", color: "#747C78", margin: "6px 0 0" }}>잠시만 기다려주세요</p>
          </div>
          <div style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "16px", padding: "24px", boxShadow: "0 1px 2px rgba(0,0,0,.05)" }}>
            <div style={{ position: "relative", borderRadius: "12px", overflow: "hidden", marginBottom: "20px", background: "#F0FAF5" }}>
              <img src={thumbOf(currentUrl)} alt="썸네일" style={{ width: "100%", height: "128px", objectFit: "cover", opacity: 0.7, display: "block" }} />
              <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,.4), transparent)" }} />
            </div>
            <p style={{ fontSize: "12px", color: "#747C78", margin: "0 0 16px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              🔗 {currentUrl}
            </p>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "14px", fontWeight: 600 }}>변환 진행률</span>
                <span style={{ fontSize: "14px", fontWeight: 700, color: "#10B45F" }}>{progress}%</span>
              </div>
              <div style={{ height: "10px", background: "#E5E8E7", borderRadius: "999px", overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${progress}%`,
                    borderRadius: "999px",
                    transition: "width .2s",
                    background: "linear-gradient(90deg, #8DDE98, #42C97A, #1BAA70)",
                  }}
                />
              </div>
              <p style={{ fontSize: "12px", color: "#747C78", margin: "8px 0 0" }}>{etaLabel}</p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {PROC_STEPS.map((st, i) => {
                const isDone = i < procStep;
                const active = i === procStep;
                return (
                  <div key={st.label} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "12px", borderRadius: "12px", background: active ? "#F0FAF5" : "transparent" }}>
                    <div
                      style={{
                        width: "24px",
                        height: "24px",
                        borderRadius: "999px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        fontSize: "12px",
                        fontWeight: 700,
                        background: isDone || active ? "#10B45F" : "#E5E8E7",
                        color: isDone || active ? "#fff" : "#747C78",
                      }}
                    >
                      {isDone ? "✓" : i + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ fontSize: "14px", fontWeight: 500, margin: 0, color: active ? "#0B7A4D" : isDone ? "#171C19" : "#747C78" }}>{st.label}</p>
                      {active && (
                        <p style={{ fontSize: "12px", color: "#747C78", margin: "2px 0 0", display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ width: "12px", height: "12px", border: "2px solid #10B45F", borderTopColor: "transparent", borderRadius: "999px", display: "inline-block", animation: "gn-spin .8s linear infinite" }} />
                          {st.desc}
                        </p>
                      )}
                    </div>
                    {isDone && <span style={{ fontSize: "12px", color: "#10B45F", fontWeight: 500 }}>완료</span>}
                  </div>
                );
              })}
            </div>
          </div>
          <button
            onClick={() => navigate("/home")}
            className="hover-dark"
            style={{ width: "100%", marginTop: "16px", padding: "12px", fontSize: "14px", color: "#747C78", background: "none", border: "none", cursor: "pointer" }}
          >
            취소
          </button>
        </div>
      </div>
    </div>
  );
}
