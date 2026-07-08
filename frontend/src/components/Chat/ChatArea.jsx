import React, { useRef, useEffect, useMemo, useState, useCallback } from "react";
import { Input, Button, Tooltip, Modal, App } from "antd";
import { SendOutlined, ClearOutlined, StopOutlined, PauseCircleOutlined, PlayCircleOutlined, ClockCircleOutlined, CodeOutlined, ExperimentOutlined, FileTextOutlined, DownloadOutlined } from "@ant-design/icons";
import { api } from "../../services/api";
import MessageItem, { downloadZip } from "./MessageItem";
import useChatStore from "../../stores/chatStore";
import useTaskStore from "../../stores/taskStore";
import useWorkerStore from "../../stores/workerStore";
const WORKER_META = {
  leader: { label: "Leader", icon: "L" },
  coder:  { label: "程序员", icon: "</>" },
  pm:     { label: "PM", icon: "PM" },
  tester: { label: "测试", icon: "T" },
};
const STAGGER_DELAY = 100;
export default function ChatArea() {
  const { message: messageApi } = App.useApp();
  const { inputValue, setInputValue, sendMessage, isSending, clearChat } = useChatStore();
  const { chatMessages, workers, streamingMessages, isPaused } = useWorkerStore();
  const { isQueued, queuePosition, taskStatus, progress, progressText, zipUrl, pauseTask, resumeTask } = useTaskStore();
  const messagesEndRef = useRef(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const typingCompleteRef = useRef(new Set());
  const prevLenRef = useRef(0);
  const [tick, setTick] = useState(0);
  const markTypingComplete = useCallback((idx) => {
    typingCompleteRef.current = new Set([...typingCompleteRef.current, idx]);
    setTick(t => t + 1);
  }, []);
  useEffect(() => {
    const len = chatMessages.length;
    if (len === 0) { setVisibleCount(0); typingCompleteRef.current = new Set(); prevLenRef.current = 0; return; }
    if (len > prevLenRef.current) {
      prevLenRef.current = len;
      if (chatMessages[len - 1]?.role === "user") {
        setVisibleCount(prev => Math.min(prev + 1, len));
        typingCompleteRef.current = new Set([...typingCompleteRef.current, len - 1]);
        setTick(t => t + 1);
      } else {
        const prev = visibleCount;
        if (prev === 0 || typingCompleteRef.current.has(prev - 1)) setVisibleCount(prev => Math.min(prev + 1, len));
      }
    }
  }, [chatMessages]);
  useEffect(() => {
    if (visibleCount >= chatMessages.length) return;
    const lastVisibleIdx = visibleCount - 1;
    if (lastVisibleIdx < 0 || typingCompleteRef.current.has(lastVisibleIdx)) {
      const timer = setTimeout(() => setVisibleCount(prev => Math.min(prev + 1, chatMessages.length)), STAGGER_DELAY);
      return () => clearTimeout(timer);
    }
  }, [visibleCount, chatMessages.length, tick]);
  const FILTER_ROLES = [
    { key: "all", label: "全部" }, { key: "leader", label: "Leader" },
    { key: "coder", label: "程序员" }, { key: "pm", label: "PM" },
    { key: "tester", label: "测试" }, { key: "user", label: "我" },
  ];
  const [activeFilter, setActiveFilter] = useState("all");
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [visibleCount, streamingMessages]);
  const activeWorker = useMemo(() => {
    for (const [id, state] of Object.entries(workers)) {
      if (state.status === "running") return { id, ...state, ...(WORKER_META[id] || {}) };
    }
    return null;
  }, [workers]);
  const lastVisibleRole = visibleCount > 0 && chatMessages[visibleCount - 1] ? chatMessages[visibleCount - 1].role : null;
  const hasPending = visibleCount < chatMessages.length;
  const [cancelling, setCancelling] = useState(false);
  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try { await api.post("/tasks/cancel"); } catch (e) { console.warn("Cancel failed:", e); }
  }, []);
  useEffect(() => { if (taskStatus !== "running") setCancelling(false); }, [taskStatus]);
  const isDiscussing = useMemo(() => {
    if (taskStatus !== "running") return false;
    const recentRoles = new Set();
    for (let i = Math.max(0, chatMessages.length - 6); i < chatMessages.length; i++) {
      if (chatMessages[i]) recentRoles.add(chatMessages[i].role);
    }
    return recentRoles.size >= 3;
  }, [chatMessages, taskStatus]);
  const filteredMessages = useMemo(() => {
    const base = activeFilter === "all" ? chatMessages.slice(0, visibleCount) : chatMessages.slice(0, visibleCount).filter(m => m.role === activeFilter);
    const result = [];
    let lastPhase = null;
    const PHASE_LABELS = { discussion: { label: "团队讨论" }, execution: { label: "执行阶段" }, summary: { label: "任务总结" } };
    for (const msg of base) {
      const phase = msg.phase || "execution";
      if (phase !== lastPhase && PHASE_LABELS[phase]) result.push({ id: "sep-" + msg.id, type: "separator", phase: phase, ...PHASE_LABELS[phase] });
      // 系统消息改为分割线形式
      if (msg.role === "system") {
        result.push({ id: "sys-" + msg.id, type: "system-separator", label: msg.content });
      } else {
        result.push(msg);
      }
      lastPhase = phase;
    }
    return result;
  }, [chatMessages, visibleCount, activeFilter]);
  const QUICK_TASKS = [
    { label: "写一个计算器", icon: <CodeOutlined />, prompt: "帮我写一个网页计算器，支持加减乘除，界面美观" },
    { label: "创建待办事项 App", icon: <FileTextOutlined />, prompt: "帮我创建一个待办事项管理应用，支持增删改查" },
    { label: "数据分析脚本", icon: <ExperimentOutlined />, prompt: "帮我用 Python 写一个 CSV 数据分析脚本，包含统计摘要和图表" },
  ];
  const handleQuickTask = (prompt) => { setInputValue(prompt); requestAnimationFrame(() => { sendMessage(prompt); }); };
  const handleSend = () => { sendMessage(inputValue); };
  const handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const handlePause = async () => { await pauseTask(); };
  const handleResume = async () => { await resumeTask(); };
  return (
    <>
      <div className="terminal-header">
        <div className="terminal-label">
          <span className={"dot " + (taskStatus === "running" ? "dot-active" : "")} />
          <span>终端</span>
          {taskStatus === "running" && activeWorker && (<span className="stage-indicator"><span className="stage-pill"><span className="stage-icon">{activeWorker.icon}</span><span className="stage-text">{activeWorker.label}</span><span className="stage-dots"><span>.</span><span>.</span><span>.</span></span></span></span>)}
          {taskStatus === "running" && !activeWorker && (<span className="stage-indicator"><span className="stage-pill">执行中<span className="stage-dots"><span>.</span><span>.</span><span>.</span></span></span></span>)}
          {isPaused && <span className="stage-pill" style={{ background: "#F59E0B" }}>已暂停</span>}
          {taskStatus === "done" && <span className="stage-pill stage-done-pill">完成</span>}
          {taskStatus === "done" && zipUrl && (<Button type="primary" size="small" icon={<DownloadOutlined />} onClick={() => downloadZip(zipUrl, "project.zip", messageApi)} style={{ marginLeft: 8, fontSize: 11 }}>下载项目</Button>)}
          {taskStatus === "failed" && <span className="stage-pill stage-fail-pill">失败</span>}
          {taskStatus === "cancelled" && <span className="stage-pill stage-cancel-pill">已停止</span>}
        </div>
        <div className="terminal-actions">
          {(taskStatus === "running" || taskStatus === "queued") && (
            <>{!isPaused ? (<Button size="small" icon={<PauseCircleOutlined />} onClick={handlePause} style={{ fontSize: 11, marginRight: 4 }}>暂停</Button>) : (<Button size="small" icon={<PlayCircleOutlined />} onClick={handleResume} style={{ fontSize: 11, marginRight: 4 }} type="primary">继续</Button>)}
            <Button danger size="small" icon={<StopOutlined />} onClick={handleCancel} loading={cancelling} style={{ fontSize: 11, marginRight: 4 }}>停止</Button></>
          )}
          {chatMessages.length > 0 && (<Button type="text" size="small" icon={<ClearOutlined />} onClick={clearChat} style={{ color: "var(--color-text-tertiary)" }}>清空</Button>)}
        </div>
      </div>
      {chatMessages.length > 0 && (<div className="chat-filter-bar"><div className="filter-chips">{FILTER_ROLES.map(f => (<button key={f.key} className={"filter-chip " + (activeFilter === f.key ? "filter-active" : "")} onClick={() => setActiveFilter(f.key)}>{f.label}</button>))}</div>{isDiscussing && <span className="discuss-badge">团队讨论</span>}</div>)}
      {taskStatus === "running" && progress > 0 && (<div className="exec-progress"><div className="exec-progress-bar"><div className="exec-progress-fill" style={{ width: Math.min(progress, 100) + "%" }} /></div><span className="exec-progress-text">{progressText || progress + "%"}</span></div>)}
      {taskStatus === "running" && activeWorker && (<div className="active-agent-bar"><span className="aab-icon">{activeWorker.icon}</span><span className="aab-label">{activeWorker.label}</span><span className="aab-phase">{activeWorker.phase || "工作中..."}</span>{activeWorker.duration > 0 && <span className="aab-duration">{activeWorker.duration}s</span>}</div>)}
      <div className="terminal-messages">
        {chatMessages.length === 0 ? (<div className="terminal-empty"><div className="empty-icon">*</div><div className="empty-hint">输入指令，AI 团队自动完成编码、审核、测试全流程</div><div className="empty-sub">点击下方快捷指令立即开始，或直接在输入框键入需求</div><div className="quick-tasks">{QUICK_TASKS.map((t, i) => (<Tooltip key={i} title={t.prompt}><button className="quick-task-btn" onClick={() => handleQuickTask(t.prompt)}><span className="qt-icon">{t.icon}</span><span className="qt-label">{t.label}</span></button></Tooltip>))}</div></div>) : (
          <>{filteredMessages.map((msg, idx) => {
            if (msg.type === "separator") { return <div key={msg.id} className="phase-separator"><span className="phase-label">{msg.label}</span></div>; }
            if (msg.type === "system-separator") { return <div key={msg.id} className="system-separator"><span className="system-sep-line" /><span className="system-sep-label">{msg.label}</span><span className="system-sep-line" /></div>; }
            const originalIdx = chatMessages.findIndex(m => m.id === msg.id);
            return <div key={msg.id} className={"msg-reveal msg-reveal-" + idx}><MessageItem message={msg} onComplete={() => markTypingComplete(originalIdx)} /></div>;
          })}
          {Object.entries(streamingMessages).map(([workerId, stream]) => (<div key={"stream-" + workerId} className="msg-reveal streaming-message"><div className="message-item"><div className="message-avatar" style={{ background: workerId === "coder" ? "#059669" : workerId === "pm" ? "#D97706" : workerId === "tester" ? "#7C3AED" : "#0891B2" }}>{WORKER_META[workerId]?.icon || workerId[0]?.toUpperCase()}</div><div className="message-content"><div className="message-role">{WORKER_META[workerId]?.label || workerId}</div><div className="message-text streaming-text">{stream.content}<span className="stream-cursor">|</span></div></div></div></div>))}</>)}
        {chatMessages.length > 0 && filteredMessages.length === 0 && <div className="filter-empty">该筛选条件下暂无消息</div>}
        {taskStatus === "running" && activeWorker && !hasPending && !isDiscussing && lastVisibleRole !== activeWorker.id && Object.keys(streamingMessages).length === 0 && (
          <div className="thinking-indicator">
            <span className="thinking-avatar" style={{background: activeWorker.id === 'coder' ? '#059669' : activeWorker.id === 'pm' ? '#D97706' : activeWorker.id === 'tester' ? '#7C3AED' : '#0891B2'}}>{activeWorker.icon}</span>
            <div className="thinking-body">
              <div className="thinking-bar">
                <span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" />
              </div>
              <span className="thinking-label">{activeWorker.label}</span>
              <span className="thinking-phase">{activeWorker.phase || '思考中...'}</span>
              {activeWorker.duration > 0 && <span className="thinking-timer">{activeWorker.duration}s</span>}
            </div>
          </div>
        )}
        {taskStatus === "running" && !activeWorker && !isDiscussing && Object.keys(streamingMessages).length === 0 && taskStatus !== 'done' && (
          <div className="thinking-indicator thinking-idle">
            <div className="thinking-pulse-ring" />
            <div className="thinking-body">
              <span className="thinking-bar">
                <span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" />
              </span>
              <span className="thinking-label">AI 团队工作中...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      {isQueued && (<div className="queued-banner"><ClockCircleOutlined /><span>任务已排队（队列中第 {queuePosition} 位），等待执行中...</span></div>)}
      <div className="terminal-input-area">
        <Input.TextArea value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入指令，Enter 发送..." autoSize={{ minRows: 1, maxRows: 4 }} disabled={isSending} style={{ flex: 1, resize: "none" }} />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={isSending} disabled={!inputValue.trim()}>发送</Button>
      </div>
    </>
  );
}