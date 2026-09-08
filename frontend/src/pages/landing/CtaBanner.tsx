import { useNavigate } from "react-router-dom";

export default function CtaBanner() {
  const navigate = useNavigate();

  return (
    <section style={{ padding: "64px 24px", background: "linear-gradient(135deg, #f0faf5 0%, #ddf5e8 100%)" }}>
      <div style={{ maxWidth: "768px", margin: "0 auto", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "24px" }}>
        <div>
          <h2 style={{ fontSize: "24px", fontWeight: 700, margin: "0 0 8px" }}>공농과 함께 더 편리한 세상을 만들어요</h2>
          <p style={{ fontSize: "14px", color: "#5c655f", margin: 0 }}>지금 시작하고, 소통의 변화를 경험해보세요!</p>
        </div>
        <button
          onClick={() => navigate("/login")}
          className="hover-primary"
          style={{
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "#10B45F",
            color: "#fff",
            fontWeight: 700,
            fontSize: "14px",
            padding: "16px 28px",
            border: "none",
            borderRadius: "16px",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          무료로 시작하기{" "}
          <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "currentColor" }}>
            <path d="M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
          </svg>
        </button>
      </div>
    </section>
  );
}
