import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp, useEasyMode } from "../state/AppContext";
import { useModal } from "../state/ModalContext";
import { thumbOf } from "../constants";
import { tabStyle } from "../styles";
import type { HistoryStatus } from "../types";
import type { NewGroupArg } from "../components/modals/NewGroupModal";

const badgeStyle = (status: HistoryStatus) => ({
  flexShrink: 0,
  fontSize: "12px",
  fontWeight: 600,
  padding: "1px 8px",
  borderRadius: "999px",
  background: status === "완료" ? "#DDF5E8" : status === "처리중" ? "#FEF9C3" : "#FEF2F2",
  color: status === "완료" ? "#0B7A4D" : status === "처리중" ? "#A16207" : "#DC2626",
});

export default function HistoryPage() {
  const easy = useEasyMode();
  const { history, groups, setCurrentUrl, removeGroup, removeItemFromGroup, requestDelete } = useApp();
  const { openModal } = useModal();
  const navigate = useNavigate();

  const [tab, setTab] = useState<string>("all");
  const [checked, setChecked] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string[]>(() => groups.map((g) => g.id));

  const viewingGroupObj = tab === "all" ? null : groups.find((g) => g.id === tab) ?? null;
  const items = tab === "all" ? history : history.filter((h) => viewingGroupObj?.itemIds.includes(h.id));
  const groupEmpty = items.length === 0 && tab !== "all";
  const showGroupList = tab === "all" && groups.length > 0;

  function play(url: string) {
    setCurrentUrl(url);
    navigate("/player");
  }
  function retry(url: string) {
    setCurrentUrl(url);
    navigate("/processing");
  }
  function toggleCheck(id: string) {
    setChecked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  }
  function openNewGroup() {
    const arg: NewGroupArg = {
      checkedIds: checked,
      onCreated: (groupId) => {
        setChecked([]);
        setTab(groupId);
      },
    };
    openModal("new-group", arg);
  }
  function deleteGroup() {
    if (tab === "all") return;
    removeGroup(tab);
    setTab("all");
  }
  function toggleExpand(id: string) {
    setExpanded((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  }

  return (
    <div style={{ maxWidth: "768px", margin: "0 auto", padding: "32px 16px", width: "100%", boxSizing: "border-box", zoom: easy ? 1.5 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 700, margin: 0 }}>시청 기록</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {checked.length > 0 && (
            <button
              onClick={openNewGroup}
              className="hover-primary"
              style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 600, background: "#10B45F", color: "#fff", border: "none", padding: "8px 14px", borderRadius: "12px", cursor: "pointer", whiteSpace: "nowrap" }}
            >
              <svg viewBox="0 0 24 24" style={{ width: "14px", height: "14px", fill: "#fff" }}>
                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
              </svg>
              그룹 만들기 ({checked.length})
            </button>
          )}
          <span style={{ fontSize: "14px", color: "#747C78", whiteSpace: "nowrap" }}>총 {history.length}건</span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
        <button onClick={() => setTab("all")} style={tabStyle(tab === "all")}>
          전체
        </button>
        {groups.map((g) => (
          <button key={g.id} onClick={() => setTab(g.id)} style={tabStyle(tab === g.id)}>
            <svg viewBox="0 0 24 24" style={{ width: "12px", height: "12px", fill: "currentColor" }}>
              <path d="M10 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2h-8l-2-2z" />
            </svg>
            {g.name}
            <span style={{ opacity: 0.6 }}>({g.itemIds.length})</span>
          </button>
        ))}
        <button
          onClick={openNewGroup}
          className="hover-outline"
          style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px", color: "#747C78", background: "none", padding: "8px 10px", borderRadius: "12px", border: "1px dashed #E5E8E7", cursor: "pointer" }}
        >
          <svg viewBox="0 0 24 24" style={{ width: "14px", height: "14px", fill: "currentColor" }}>
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
          </svg>
          새 그룹
        </button>
      </div>

      {viewingGroupObj && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", padding: "0 4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "#10B45F" }}>
              <path d="M10 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2h-8l-2-2z" />
            </svg>
            <span style={{ fontSize: "14px", fontWeight: 700 }}>{viewingGroupObj.name}</span>
          </div>
          <button onClick={deleteGroup} style={{ background: "none", border: "none", fontSize: "12px", color: "#f87171", cursor: "pointer" }}>
            그룹 삭제
          </button>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {items.map((h) => {
          const isChecked = checked.includes(h.id);
          const done = h.status === "완료";
          const failed = h.status === "실패";
          return (
            <div
              key={h.id}
              style={{ background: "#fff", border: isChecked ? "1px solid #10B45F" : "1px solid #E5E8E7", borderRadius: "16px", padding: "16px", display: "flex", gap: "16px" }}
            >
              <button
                onClick={() => toggleCheck(h.id)}
                style={{
                  flexShrink: 0,
                  alignSelf: "flex-start",
                  marginTop: "2px",
                  width: "20px",
                  height: "20px",
                  borderRadius: "6px",
                  border: `2px solid ${isChecked ? "#10B45F" : "#E5E8E7"}`,
                  background: isChecked ? "#10B45F" : "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                <svg viewBox="0 0 24 24" style={{ width: "12px", height: "12px", fill: "#fff", opacity: isChecked ? 1 : 0 }}>
                  <path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                </svg>
              </button>
              <div
                onClick={() => done && play(h.url)}
                style={{ width: "112px", flexShrink: 0, borderRadius: "12px", overflow: "hidden", background: "#F0FAF5", position: "relative", aspectRatio: "16 / 9", cursor: done ? "pointer" : "default" }}
              >
                <img src={thumbOf(h.url)} alt={h.title} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                {done && (
                  <span style={{ position: "absolute", top: "6px", left: "6px", fontSize: "10px", fontWeight: 600, background: "#10B45F", color: "#fff", padding: "1px 6px", borderRadius: "999px" }}>
                    수어 지원
                  </span>
                )}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", justifyContent: "space-between" }}>
                  <p style={{ fontSize: "14px", fontWeight: 600, margin: 0, lineHeight: 1.4 }}>{h.title}</p>
                  <span style={badgeStyle(h.status)}>{h.status}</span>
                </div>
                <p style={{ fontSize: "12px", color: "#747C78", margin: "6px 0 0" }}>
                  {h.date} · {h.duration}
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "12px", flexWrap: "wrap" }}>
                  {done && (
                    <button
                      onClick={() => play(h.url)}
                      className="hover-primary"
                      style={{ fontSize: "12px", fontWeight: 600, background: "#10B45F", color: "#fff", border: "none", padding: "8px 14px", borderRadius: "12px", cursor: "pointer", whiteSpace: "nowrap" }}
                    >
                      다시 재생
                    </button>
                  )}
                  {failed && (
                    <button
                      onClick={() => retry(h.url)}
                      className="hover-outline"
                      style={{ fontSize: "12px", fontWeight: 600, background: "#fff", border: "1px solid #E5E8E7", padding: "8px 14px", borderRadius: "12px", cursor: "pointer", whiteSpace: "nowrap" }}
                    >
                      재처리 요청
                    </button>
                  )}
                  <button
                    onClick={() => openModal("add-group", { itemId: h.id })}
                    className="hover-green"
                    style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px", color: "#747C78", background: "none", border: "none", padding: "8px 6px", cursor: "pointer", whiteSpace: "nowrap" }}
                  >
                    <svg viewBox="0 0 24 24" style={{ width: "14px", height: "14px", fill: "currentColor" }}>
                      <path d="M10 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2h-8l-2-2z" />
                    </svg>
                    그룹에 추가
                  </button>
                  <button
                    onClick={() => requestDelete({ id: h.id, title: h.title })}
                    className="hover-red"
                    style={{ fontSize: "12px", color: "#747C78", background: "none", border: "none", padding: "8px 6px", cursor: "pointer" }}
                  >
                    삭제
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        {groupEmpty && <div style={{ textAlign: "center", padding: "40px 0", fontSize: "14px", color: "#747C78" }}>이 그룹에 영상이 없습니다</div>}
      </div>

      {showGroupList && (
        <div style={{ marginTop: "32px" }}>
          <h2 style={{ fontSize: "14px", fontWeight: 700, margin: "0 0 12px" }}>내 그룹</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {groups.map((g) => {
              const gitems = history.filter((h) => g.itemIds.includes(h.id));
              const isExpanded = expanded.includes(g.id);
              return (
                <div key={g.id} style={{ background: "#fff", border: "1px solid #E5E8E7", borderRadius: "16px", overflow: "hidden" }}>
                  <button
                    onClick={() => toggleExpand(g.id)}
                    className="hover-muted"
                    style={{ width: "100%", display: "flex", alignItems: "center", gap: "12px", padding: "14px 16px", background: "none", border: "none", cursor: "pointer" }}
                  >
                    <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", fill: "#10B45F", flexShrink: 0 }}>
                      <path d="M10 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2h-8l-2-2z" />
                    </svg>
                    <span style={{ flex: 1, fontSize: "14px", fontWeight: 600, textAlign: "left" }}>{g.name}</span>
                    <span style={{ fontSize: "12px", color: "#747C78" }}>{g.itemIds.length}개</span>
                    <svg
                      viewBox="0 0 24 24"
                      style={{ width: "16px", height: "16px", fill: "#747C78", transform: isExpanded ? "rotate(180deg)" : "none", transition: "transform .2s" }}
                    >
                      <path d="M7 10l5 5 5-5z" />
                    </svg>
                  </button>
                  {isExpanded && (
                    <div style={{ borderTop: "1px solid #E5E8E7" }}>
                      {gitems.map((h) => (
                        <div key={h.id} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "12px 16px", borderBottom: "1px solid #F0F1F0" }}>
                          <div style={{ width: "64px", flexShrink: 0, borderRadius: "8px", overflow: "hidden", background: "#F0FAF5", aspectRatio: "16 / 9" }}>
                            <img src={thumbOf(h.url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                          </div>
                          <p style={{ flex: 1, fontSize: "12px", fontWeight: 500, margin: 0, minWidth: 0, lineHeight: 1.45 }}>{h.title}</p>
                          <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
                            <button
                              onClick={() => play(h.url)}
                              className="hover-secondary"
                              style={{ fontSize: "10px", fontWeight: 600, background: "#F0FAF5", color: "#0B7A4D", border: "none", padding: "6px 10px", borderRadius: "8px", cursor: "pointer" }}
                            >
                              재생
                            </button>
                            <button
                              onClick={() => removeItemFromGroup(g.id, h.id)}
                              className="hover-red"
                              style={{ fontSize: "10px", color: "#747C78", background: "none", border: "none", padding: "6px", cursor: "pointer" }}
                            >
                              제거
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
