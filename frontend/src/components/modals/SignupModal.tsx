import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ModalShell from "../ModalShell";
import { useModal } from "../../state/ModalContext";

interface SignupForm {
  name: string;
  id: string;
  email: string;
  pw: string;
  pw2: string;
}

const FIELDS: { key: keyof SignupForm; label: string; type: string; placeholder: string }[] = [
  { key: "name", label: "이름", type: "text", placeholder: "실명을 입력하세요" },
  { key: "id", label: "아이디", type: "text", placeholder: "4자 이상" },
  { key: "email", label: "이메일", type: "email", placeholder: "example@email.com" },
  { key: "pw", label: "비밀번호", type: "password", placeholder: "6자 이상" },
  { key: "pw2", label: "비밀번호 확인", type: "password", placeholder: "비밀번호 재입력" },
];

export default function SignupModal() {
  const { closeModal } = useModal();
  const navigate = useNavigate();
  const [step, setStep] = useState<"form" | "done">("form");
  const [su, setSu] = useState<SignupForm>({ name: "", id: "", email: "", pw: "", pw2: "" });
  const [agree, setAgree] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof SignupForm | "agree", string>>>({});

  function submit() {
    const e: typeof errors = {};
    if (!su.name.trim()) e.name = "이름을 입력하세요.";
    if (!su.id.trim() || su.id.length < 4) e.id = "아이디는 4자 이상이어야 합니다.";
    if (!su.email.includes("@")) e.email = "올바른 이메일을 입력하세요.";
    if (su.pw.length < 6) e.pw = "비밀번호는 6자 이상이어야 합니다.";
    if (su.pw !== su.pw2) e.pw2 = "비밀번호가 일치하지 않습니다.";
    if (!agree) e.agree = "이용약관에 동의해주세요.";
    if (Object.keys(e).length) {
      setErrors(e);
      return;
    }
    setErrors({});
    setStep("done");
  }

  function goLogin() {
    closeModal();
    navigate("/onboarding", { state: { name: su.name.trim() } });
  }

  return (
    <ModalShell title={step === "done" ? "회원가입 완료" : "회원가입"}>
      {step === "done" ? (
        <div style={{ textAlign: "center", padding: "8px 0" }}>
          <div
            style={{
              width: "56px",
              height: "56px",
              background: "#F0FAF5",
              borderRadius: "999px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <svg viewBox="0 0 24 24" style={{ width: "28px", height: "28px", fill: "#10B45F" }}>
              <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
            </svg>
          </div>
          <p style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 4px" }}>환영합니다, {su.name}님!</p>
          <p style={{ fontSize: "14px", color: "#747C78", margin: "0 0 24px" }}>공농 회원가입이 완료되었습니다.</p>
          <button
            onClick={goLogin}
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
            로그인하기
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#747C78", marginBottom: "6px" }}>
                {f.label}
              </label>
              <input
                type={f.type}
                className="gn-input"
                value={su[f.key]}
                onChange={(e) => setSu((p) => ({ ...p, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  border: "1px solid #E5E8E7",
                  borderRadius: "12px",
                  padding: "12px 16px",
                  fontSize: "14px",
                }}
              />
              {errors[f.key] && <p style={{ fontSize: "12px", color: "#EF4444", margin: "4px 0 0" }}>{errors[f.key]}</p>}
            </div>
          ))}
          <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", paddingTop: "4px" }}>
            <input
              type="checkbox"
              checked={agree}
              onChange={() => setAgree((a) => !a)}
              style={{ width: "16px", height: "16px", accentColor: "#10B45F" }}
            />
            <span style={{ fontSize: "12px", color: "#747C78" }}>이용약관 및 개인정보처리방침에 동의합니다</span>
          </label>
          {errors.agree && <p style={{ fontSize: "12px", color: "#EF4444", margin: 0 }}>{errors.agree}</p>}
          <button
            onClick={submit}
            className="hover-primary"
            style={{
              width: "100%",
              padding: "12px",
              marginTop: "8px",
              background: "#10B45F",
              color: "#fff",
              border: "none",
              borderRadius: "12px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            가입하기
          </button>
        </div>
      )}
    </ModalShell>
  );
}
