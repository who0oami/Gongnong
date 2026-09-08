import { useState } from "react";
import ModalShell from "../ModalShell";
import TextField from "../TextField";
import { useModal } from "../../state/ModalContext";

export default function FindIdModal() {
  const { closeModal } = useModal();
  const [email, setEmail] = useState("");
  const [result, setResult] = useState("");

  function submit() {
    if (!email.trim()) return;
    setResult("gongnong_user");
  }

  return (
    <ModalShell title="아이디 찾기">
      {result ? (
        <div style={{ textAlign: "center", padding: "8px 0" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              background: "#F0FAF5",
              borderRadius: "999px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 12px",
            }}
          >
            <svg viewBox="0 0 24 24" style={{ width: "24px", height: "24px", fill: "#10B45F" }}>
              <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
            </svg>
          </div>
          <p style={{ fontSize: "14px", color: "#747C78", margin: "0 0 4px" }}>회원님의 아이디는</p>
          <p style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 20px" }}>{result}</p>
          <button
            onClick={closeModal}
            className="hover-primary"
            style={{
              width: "100%",
              padding: "12px",
              background: "#10B45F",
              color: "#fff",
              border: "none",
              borderRadius: "12px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            확인
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <p style={{ fontSize: "14px", color: "#747C78", margin: 0 }}>가입 시 등록한 이메일 주소를 입력하세요.</p>
          <TextField
            id="fi-mail"
            label="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="example@email.com"
          />
          <button
            onClick={submit}
            className="hover-primary"
            style={{
              width: "100%",
              padding: "12px",
              background: "#10B45F",
              color: "#fff",
              border: "none",
              borderRadius: "12px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            아이디 찾기
          </button>
        </div>
      )}
    </ModalShell>
  );
}
