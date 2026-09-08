import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useModal } from "../state/ModalContext";
import logo from "../assets/logo.png";

export default function LoginPage() {
  const navigate = useNavigate();
  const { openModal } = useModal();
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");

  function submit() {
    if (!id || !pw) {
      setError("아이디와 비밀번호를 입력해주세요.");
      return;
    }
    setError("");
    navigate("/home");
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#F0FAF5",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 16px",
      }}
    >
      <div style={{ width: "100%", maxWidth: "384px" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <img src={logo} alt="공농" style={{ height: "48px", width: "auto" }} />
          <p style={{ fontSize: "14px", color: "#747C78", margin: "8px 0 0" }}>수어로 연결되는 더 넓은 세상</p>
        </div>
        <div
          style={{
            background: "#fff",
            border: "1px solid #E5E8E7",
            borderRadius: "16px",
            padding: "32px",
            boxShadow: "0 1px 2px rgba(0,0,0,.05)",
          }}
        >
          <h1 style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 20px" }}>로그인</h1>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label htmlFor="gn-id" style={{ display: "block", fontSize: "14px", fontWeight: 500, marginBottom: "6px" }}>
                아이디
              </label>
              <input
                id="gn-id"
                className="gn-input"
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder="아이디를 입력하세요"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "12px 16px",
                  border: "1px solid #E5E8E7",
                  borderRadius: "12px",
                  fontSize: "14px",
                }}
              />
            </div>
            <div>
              <label htmlFor="gn-pw" style={{ display: "block", fontSize: "14px", fontWeight: 500, marginBottom: "6px" }}>
                비밀번호
              </label>
              <input
                id="gn-pw"
                type="password"
                className="gn-input"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder="비밀번호를 입력하세요"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "12px 16px",
                  border: "1px solid #E5E8E7",
                  borderRadius: "12px",
                  fontSize: "14px",
                }}
              />
            </div>
            {error && <p style={{ fontSize: "14px", color: "#EF4444", margin: 0 }}>{error}</p>}
            <button
              onClick={submit}
              className="hover-primary"
              style={{
                width: "100%",
                padding: "14px",
                background: "#10B45F",
                color: "#fff",
                border: "none",
                borderRadius: "12px",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              로그인
            </button>
          </div>
          <div
            style={{
              marginTop: "16px",
              paddingTop: "16px",
              borderTop: "1px solid #E5E8E7",
              display: "flex",
              justifyContent: "center",
              gap: "16px",
              fontSize: "12px",
              color: "#747C78",
            }}
          >
            <button
              onClick={() => openModal("find-id")}
              className="hover-dark"
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "inherit", fontSize: "inherit" }}
            >
              아이디 찾기
            </button>
            <span>·</span>
            <button
              onClick={() => openModal("find-pw")}
              className="hover-dark"
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "inherit", fontSize: "inherit" }}
            >
              비밀번호 찾기
            </button>
            <span>·</span>
            <button
              onClick={() => openModal("signup")}
              className="hover-green"
              style={{
                background: "none",
                border: "none",
                padding: 0,
                cursor: "pointer",
                color: "inherit",
                fontSize: "inherit",
                fontWeight: 500,
              }}
            >
              회원가입
            </button>
          </div>
        </div>
        <p style={{ textAlign: "center", fontSize: "12px", color: "#747C78", margin: "20px 0 0" }}>
          로그인하면 공농 서비스를 이용할 수 있습니다
        </p>
      </div>
    </div>
  );
}
