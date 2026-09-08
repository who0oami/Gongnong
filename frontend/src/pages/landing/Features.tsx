import { FEATURES } from "../../constants";

export default function Features() {
  return (
    <section id="features" style={{ background: "#F7F8F8", padding: "64px 24px", scrollMarginTop: "64px" }}>
      <div style={{ maxWidth: "1024px", margin: "0 auto" }}>
        <h2 style={{ fontSize: "24px", fontWeight: 700, textAlign: "center", margin: "0 0 48px" }}>
          <span style={{ color: "#10B45F" }}>공농</span>은 어떤 기능을 제공해요
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px" }}>
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="hover-lift"
              style={{
                background: "#fff",
                border: "1px solid #E5E8E7",
                borderRadius: "16px",
                padding: "20px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  borderRadius: "12px",
                  background: "#F0FAF5",
                  color: "#10B45F",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <svg viewBox="0 0 24 24" style={{ width: "28px", height: "28px", fill: "currentColor" }}>
                  <path d={f.d} />
                </svg>
              </div>
              <h3 style={{ fontSize: "14px", fontWeight: 700, margin: 0 }}>{f.title}</h3>
              <p style={{ fontSize: "12px", color: "#747C78", lineHeight: 1.65, margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
