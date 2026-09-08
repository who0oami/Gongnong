import { useState } from "react";
import { useNavigate } from "react-router-dom";
import heroBase from "../../assets/hero-base.png";
import spark1 from "../../assets/spark1.png";
import spark2 from "../../assets/spark2.png";
import spark3 from "../../assets/spark3.png";

const BAR_HEIGHTS: [number, number][] = [
  [6, 0],
  [11, 0.05],
  [17, 0.1],
  [12, 0.15],
  [6, 0.2],
  [14, 0.25],
  [8, 0.3],
];

export default function Hero() {
  const navigate = useNavigate();
  const [hVoice, setHVoice] = useState(false);
  const [hHand, setHHand] = useState(false);
  const [hPlay, setHPlay] = useState(false);

  return (
    <section
      style={{
        maxWidth: "1152px",
        margin: "0 auto",
        padding: "64px 24px 80px",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
        gap: "40px",
        alignItems: "center",
      }}
    >
      <div>
        <h1 style={{ fontSize: "48px", fontWeight: 700, lineHeight: 1.18, margin: "0 0 12px", letterSpacing: "-0.02em" }}>
          영상 속 말을
          <br />
          <span style={{ color: "#10B45F" }}>
            수어로 만나다
            <br />
          </span>
        </h1>
        <p style={{ fontSize: "16px", color: "#747C78", lineHeight: 1.75, margin: "0 0 32px" }}>
          유튜브의 영상을 실시간으로 인식하고
          <br />
          수어로 변환해주는 서비스
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px", marginBottom: "24px" }}>
          <button
            onClick={() => navigate("/login")}
            className="hover-primary"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "#10B45F",
              color: "#fff",
              fontWeight: 700,
              fontSize: "14px",
              padding: "14px 24px",
              border: "none",
              borderRadius: "16px",
              cursor: "pointer",
              boxShadow: "0 1px 2px rgba(0,0,0,.05)",
              whiteSpace: "nowrap",
            }}
          >
            서비스 시작하기{" "}
            <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "currentColor" }}>
              <path d="M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
            </svg>
          </button>
          <a
            href="#about"
            className="hover-outline"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              border: "1px solid #E5E8E7",
              background: "#fff",
              color: "#171C19",
              fontWeight: 600,
              fontSize: "14px",
              padding: "14px 24px",
              borderRadius: "16px",
              cursor: "pointer",
              whiteSpace: "nowrap",
              textDecoration: "none",
            }}
          >
            서비스 소개 보기
          </a>
        </div>
      </div>

      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", minHeight: "380px" }}>
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            transform: "translate(-50%, -50%)",
            width: "340px",
            height: "320px",
            borderRadius: "50%",
            background: "radial-gradient(ellipse, rgba(16,180,95,.08) 0%, transparent 68%)",
            pointerEvents: "none",
          }}
        />

        <div
          onMouseEnter={() => setHVoice(true)}
          onMouseLeave={() => setHVoice(false)}
          style={{
            position: "absolute",
            top: "6%",
            left: 0,
            zIndex: 20,
            width: "72px",
            height: "72px",
            borderRadius: "999px",
            background: "#fff",
            boxShadow: "0 4px 18px rgba(0,0,0,.09)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "gn-float-a 5.2s ease-in-out infinite",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "30px" }}>
            {BAR_HEIGHTS.map(([h, delay], i) => (
              <span
                key={i}
                style={{
                  width: "4px",
                  height: `${h}px`,
                  borderRadius: "999px",
                  background: "#10B45F",
                  transformOrigin: "bottom center",
                  animation: hVoice ? `gn-bar .34s ease-in-out ${delay}s infinite alternate` : "none",
                }}
              />
            ))}
          </div>
        </div>

        <div
          onMouseEnter={() => setHHand(true)}
          onMouseLeave={() => setHHand(false)}
          style={{
            position: "absolute",
            top: "10%",
            right: "2%",
            zIndex: 20,
            width: "68px",
            height: "68px",
            borderRadius: "999px",
            background: "#fff",
            boxShadow: "0 4px 18px rgba(0,0,0,.09)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "gn-float-b 6.1s ease-in-out .6s infinite",
          }}
        >
          <svg
            viewBox="0 0 24 24"
            style={{ width: "33px", height: "33px", fill: "#10B45F", animation: hHand ? "gn-hand-shake .7s ease-in-out infinite" : "none" }}
          >
            <path d="M9 11.24V7.5C9 6.12 10.12 5 11.5 5S14 6.12 14 7.5v3.74c1.21-.81 2-2.18 2-3.74C16 5.01 13.99 3 11.5 3S7 5.01 7 7.5c0 1.56.79 2.93 2 3.74zm9.84 4.63-4.54-2.26c-.17-.07-.35-.11-.54-.11H13v-6c0-.83-.67-1.5-1.5-1.5S10 6.67 10 7.5v10.74l-3.43-.72c-.08-.01-.15-.03-.24-.03-.31 0-.59.13-.79.33l-.79.8 4.94 4.94c.27.27.65.44 1.06.44h6.79c.75 0 1.33-.55 1.44-1.28l.75-5.27c.01-.07.02-.14.02-.2 0-.62-.38-1.16-.91-1.38z" />
          </svg>
        </div>

        <div
          onMouseEnter={() => setHPlay(true)}
          onMouseLeave={() => setHPlay(false)}
          style={{
            position: "absolute",
            top: "57%",
            right: "4%",
            zIndex: 20,
            width: "64px",
            height: "64px",
            borderRadius: "999px",
            background: "#fff",
            boxShadow: "0 4px 18px rgba(0,0,0,.09)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "gn-float-c 5.6s ease-in-out 1.1s infinite",
          }}
        >
          <svg viewBox="0 0 24 24" style={{ width: "29px", height: "29px", fill: "#10B45F", animation: hPlay ? "gn-nudge .9s ease-in-out infinite" : "none" }}>
            <path d="M8 5v14l11-7z" />
          </svg>
        </div>

        <div style={{ position: "relative", zIndex: 10, width: "128%", maxWidth: "520px", flexShrink: 0, aspectRatio: "1886 / 1368" }}>
          <img src={heroBase} alt="공농이" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
          <img
            src={spark1}
            alt=""
            style={{
              position: "absolute",
              left: "18.13%",
              top: "48.61%",
              width: "3.45%",
              height: "2.41%",
              transformOrigin: "50% 50%",
              animation: "gn-spark 2.6s ease-in-out 0s infinite",
              willChange: "transform",
            }}
          />
          <img
            src={spark2}
            alt=""
            style={{
              position: "absolute",
              left: "19.88%",
              top: "43.93%",
              width: "3.23%",
              height: "4.09%",
              transformOrigin: "50% 50%",
              animation: "gn-spark 2.6s ease-in-out .22s infinite",
              willChange: "transform",
            }}
          />
          <img
            src={spark3}
            alt=""
            style={{
              position: "absolute",
              left: "23.86%",
              top: "41.45%",
              width: "1.80%",
              height: "4.61%",
              transformOrigin: "50% 50%",
              animation: "gn-spark 2.6s ease-in-out .44s infinite",
              willChange: "transform",
            }}
          />
        </div>
      </div>
    </section>
  );
}
