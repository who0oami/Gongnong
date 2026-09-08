import { STEPS } from "../../constants";

export default function HowItWorks() {
  return (
    <section id="how" style={{ padding: "64px 24px", background: "#fff", scrollMarginTop: "64px" }}>
      <div style={{ maxWidth: "896px", margin: "0 auto" }}>
        <h2 style={{ fontSize: "24px", fontWeight: 700, textAlign: "center", margin: "0 0 48px" }}>이렇게 사용해요</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "16px" }}>
          {STEPS.map((s) => (
            <div key={s.num} style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "12px" }}>
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "999px",
                  background: "#10B45F",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 1px 3px rgba(0,0,0,.1)",
                }}
              >
                <svg viewBox="0 0 24 24" style={{ width: "24px", height: "24px", fill: "#fff" }}>
                  <path d={s.d} />
                </svg>
              </div>
              <div>
                <p style={{ fontSize: "12px", fontWeight: 700, color: "#10B45F", margin: "0 0 4px" }}>{s.num}</p>
                <h3 style={{ fontSize: "14px", fontWeight: 700, margin: "0 0 4px" }}>{s.title}</h3>
                <p style={{ fontSize: "12px", color: "#747C78", lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
