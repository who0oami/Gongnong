import { useState } from "react";
import ModalShell from "../ModalShell";
import { useApp } from "../../state/AppContext";
import { useModal } from "../../state/ModalContext";

export interface NewGroupArg {
  checkedIds: string[];
  onCreated: (groupId: string) => void;
}

export default function NewGroupModal({ arg }: { arg: NewGroupArg }) {
  const { addGroup } = useApp();
  const { closeModal } = useModal();
  const [name, setName] = useState("");

  const hint =
    arg.checkedIds.length > 0 ? `${arg.checkedIds.length}개의 영상으로 그룹을 만듭니다.` : "새 그룹의 이름을 입력하세요.";

  function create() {
    const trimmed = name.trim();
    if (!trimmed) return;
    const id = "g" + Date.now();
    addGroup({ id, name: trimmed, itemIds: [...arg.checkedIds] });
    arg.onCreated(id);
    closeModal();
  }

  return (
    <ModalShell title="새 그룹 만들기">
      <p style={{ fontSize: "14px", color: "#747C78", margin: "0 0 12px" }}>{hint}</p>
      <input
        className="gn-input"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="그룹 이름 입력..."
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: "1px solid #E5E8E7",
          borderRadius: "12px",
          padding: "12px 16px",
          fontSize: "14px",
        }}
      />
      <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
        <button
          onClick={closeModal}
          className="hover-muted"
          style={{
            flex: 1,
            padding: "12px",
            fontSize: "14px",
            color: "#747C78",
            background: "#fff",
            border: "1px solid #E5E8E7",
            borderRadius: "12px",
            cursor: "pointer",
          }}
        >
          취소
        </button>
        <button
          onClick={create}
          style={{
            flex: 1,
            padding: "12px",
            fontSize: "14px",
            fontWeight: 600,
            background: "#10B45F",
            color: "#fff",
            border: "none",
            borderRadius: "12px",
            cursor: "pointer",
            opacity: name.trim() ? 1 : 0.4,
          }}
        >
          만들기
        </button>
      </div>
    </ModalShell>
  );
}
