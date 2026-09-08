import { useNavigate } from "react-router-dom";
import logo from "../../assets/logo.png";

export default function NavHeader() {
  const navigate = useNavigate();

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        background: "rgba(255,255,255,.9)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid #E5E8E7",
      }}
    >
      <div
        style={{
          maxWidth: "1152px",
          margin: "0 auto",
          padding: "0 24px",
          height: "64px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "24px",
        }}
      >
        <img src={logo} alt="공농" style={{ height: "36px", width: "auto" }} />
        <nav style={{ display: "flex", alignItems: "center", gap: "28px", fontSize: "14px", fontWeight: 500, color: "#747C78" }}>
          <a href="#about" className="hover-dark" style={{ color: "inherit", textDecoration: "none" }}>
            서비스 소개
          </a>
          <a href="#features" className="hover-dark" style={{ color: "inherit", textDecoration: "none" }}>
            기능
          </a>
          <a href="#how" className="hover-dark" style={{ color: "inherit", textDecoration: "none" }}>
            이용 방법
          </a>
          <a href="#faq" className="hover-dark" style={{ color: "inherit", textDecoration: "none" }}>
            FAQ
          </a>
        </nav>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={() => navigate("/login")}
            className="hover-muted"
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "#171C19",
              background: "none",
              border: "none",
              padding: "8px 16px",
              borderRadius: "12px",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            로그인
          </button>
          <button
            onClick={() => navigate("/login")}
            className="hover-primary"
            style={{
              fontSize: "14px",
              fontWeight: 700,
              background: "#10B45F",
              color: "#fff",
              border: "none",
              padding: "9px 16px",
              borderRadius: "12px",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            회원가입
          </button>
        </div>
      </div>
    </header>
  );
}
