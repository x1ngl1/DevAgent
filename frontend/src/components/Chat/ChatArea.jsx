import React, { useRef, useEffect, useMemo, useState, useCallback } from "react";
import { Input, Button, Tooltip, Modal, App, Upload, Tag } from "antd";
import { SendOutlined, ClearOutlined, StopOutlined, PauseCircleOutlined, PlayCircleOutlined, ClockCircleOutlined, CodeOutlined, ExperimentOutlined, FileTextOutlined, DownloadOutlined, UploadOutlined, FileAddOutlined, PercentageOutlined, BugOutlined, AimOutlined, DeleteOutlined } from "@ant-design/icons";
import { api, uploadCodeFile } from "../../services/api";
import MessageItem, { downloadZip } from "./MessageItem";
import useChatStore from "../../stores/chatStore";
import useTaskStore from "../../stores/taskStore";
import useWorkerStore from "../../stores/workerStore";

const WORKER_META = {
  leader: { label: "Leader", icon: "L" },
  coder:  { label: "测试生成", icon: "</>" },
  pm:     { label: "PM", icon: "PM" },
  tester: { label: "测试执行", icon: "T" },
};
const STAGGER_DELAY = 100;

export default function ChatArea() {
  const { message: messageApi } = App.useApp();
  const { inputValue, setInputValue, sendMessage, isSending, clearChat, uploadedFiles, addUploadedFile, removeUploadedFile, clearUploadedFiles } = useChatStore();
  const { chatMessages, workers, streamingMessages, isPaused } = useWorkerStore();
  const { isQueued, queuePosition, taskStatus, progress, progressText, zipUrl, pauseTask, resumeTask } = useTaskStore();
  const messagesEndRef = useRef(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const typingCompleteRef = useRef(new Set());
  const prevLenRef = useRef(0);
  const [tick, setTick] = useState(0);
  const fileInputRef = useRef(null);

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
    { key: "coder", label: "测试生成" }, { key: "pm", label: "PM" },
    { key: "tester", label: "测试执行" }, { key: "user", label: "我" },
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
    const PHASE_LABELS = { discussion: { label: "团队讨论" }, execution: { label: "执行阶段" }, summary: { label: "测试总结" } };
    for (const msg of base) {
      const phase = msg.phase || "execution";
      if (phase !== lastPhase && PHASE_LABELS[phase]) result.push({ id: "sep-" + msg.id, type: "separator", phase: phase, ...PHASE_LABELS[phase] });
      if (msg.role === "system") {
        result.push({ id: "sys-" + msg.id, type: "system-separator", label: msg.content });
      } else {
        result.push(msg);
      }
      lastPhase = phase;
    }
    return result;
  }, [chatMessages, visibleCount, activeFilter]);

  // 快捷测试任务按钮
  const QUICK_TASKS = [
    { label: "测试计算函数", icon: <PercentageOutlined />, prompt: "请分析以下代码并生成单元测试：\ndef add(a, b): return a + b\ndef divide(a, b):\n    if b == 0: raise ValueError('除数不能为0')\n    return a / b" },
    { label: "测试数据处理", icon: <ExperimentOutlined />, prompt: "请分析以下代码并生成单元测试：\ndef process_list(data):\n    if not data: return []\n    return [x * 2 for x in data if x > 0]" },
    { label: "上传代码文件", icon: <UploadOutlined />, prompt: "", isUpload: true },
  ];

  // 文件上传处理
  const handleFileUpload = useCallback(async (file) => {
    const allowedExtensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      messageApi.error(`不支持的文件类型: ${ext}，支持: ${allowedExtensions.join(', ')}`);
      return Upload.LIST_IGNORE;
    }
    addUploadedFile(file);
    return false; // 阻止默认上传
  }, [addUploadedFile, messageApi]);

  const handleQuickTask = (task) => {
    if (task.isUpload) {
      fileInputRef.current?.click();
      return;
    }
    setInputValue(task.prompt);
    requestAnimationFrame(() => { sendMessage(task.prompt); });
  };

  const handleSend = () => { sendMessage(inputValue); };
  const handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const handlePause = async () => { await pauseTask(); };
  const handleResume = async () => { await resumeTask(); };

  // 检测消息中是否包含覆盖率数据
  const getCoverageTag = (msg) => {
    if (!msg.content) return null;
    const match = msg.content.match(/覆盖率\s*[:：]\s*(\d+(?:\.\d+)?)%/);
    if (match) {
      const pct = parseFloat(match[1]);
      return <Tag color={pct >= 80 ? "success" : pct >= 60 ? "warning" : "error"} style={{ marginLeft: 8 }}>覆盖率: {pct}%</Tag>;
    }
    return null;
  };

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
          {taskStatus === "done" && zipUrl && (<Button type="primary" size="small" icon={<DownloadOutlined />} onClick={() => downloadZip(zipUrl, "test-report.zip", messageApi)} style={{ marginLeft: 8, fontSize: 11 }}>下载测试报告</Button>)}
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
        {chatMessages.length === 0 ? (<div className="terminal-empty"><div className="empty-icon"><BugOutlined /></div><div className="empty-hint">上传代码文件，AI 团队自动生成单元测试</div><div className="empty-sub">支持 .py / .js / .ts / .java 等语言，系统将分析代码结构并生成全面测试</div><div className="quick-tasks">{QUICK_TASKS.map((t, i) => (<Tooltip key={i} title={t.isUpload ? "点击选择代码文件" : t.prompt.slice(0, 50) + "..."}><button className="quick-task-btn" onClick={() => handleQuickTask(t)}><span className="qt-icon">{t.icon}</span><span className="qt-label">{t.label}</span></button></Tooltip>))}</div></div>) : (
          <>{filteredMessages.map((msg, idx) => {
            if (msg.type === "separator") { return <div key={msg.id} className="phase-separator"><span className="phase-label">{msg.label}</span></div>; }
            if (msg.type === "system-separator") { return <div key={msg.id} className="system-separator"><span className="system-sep-line" /><span className="system-sep-label">{msg.label}</span><span className="system-sep-line" /></div>; }
            const originalIdx = chatMessages.findIndex(m => m.id === msg.id);
            return <div key={msg.id} className={"msg-reveal msg-reveal-" + idx}>
              <MessageItem message={msg} onComplete={() => markTypingComplete(originalIdx)} />
              {getCoverageTag(msg) && <div style={{ marginTop: 4, marginLeft: 48 }}>{getCoverageTag(msg)}</div>}
            </div>;
          })}
          {Object.entries(streamingMessages).map(([workerId, stream]) => (<div key={"stream-" + workerId} className="msg-reveal streaming-message"><div className="message-item"><div className={"message-avatar message-avatar-" + workerId}>{WORKER_META[workerId]?.icon || workerId[0]?.toUpperCase()}</div><div className="message-content"><div className="message-role">{WORKER_META[workerId]?.label || workerId}</div><div className="message-text streaming-text">{stream.content}<span className="stream-cursor">|</span></div></div></div></div>))}</>)}
        {chatMessages.length > 0 && filteredMessages.length === 0 && <div className="filter-empty">该筛选条件下暂无消息</div>}
        {taskStatus === "running" && activeWorker && !hasPending && !isDiscussing && lastVisibleRole !== activeWorker.id && Object.keys(streamingMessages).length === 0 && (
          <div className="thinking-indicator">
            <span className={"thinking-avatar thinking-avatar-" + activeWorker.id}>{activeWorker.icon}</span>
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
              <span className="thinking-label">AI 测试团队工作中...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      {isQueued && (<div className="queued-banner"><ClockCircleOutlined /><span>任务已排队（队列中第 {queuePosition} 位），等待执行中...</span></div>)}

      {/* 上传文件列表显示 */}
      {uploadedFiles.length > 0 && (
        <div className="uploaded-files-bar">
          {uploadedFiles.map((f) => (
            <div key={f.id} className="uploaded-file-item">
              <FileAddOutlined style={{ marginRight: 6 }} />
              <span className="uploaded-file-name">{f.name}</span>
              <span className="uploaded-file-size">({(f.size / 1024).toFixed(1)} KB)</span>
              <Button type="text" size="small" icon={<DeleteOutlined />} onClick={() => removeUploadedFile(f.id)} style={{ marginLeft: 8, color: '#ef4444' }} />
            </div>
          ))}
        </div>
      )}

      {/* 输入区域 + 上传按钮 */}
      <div className="terminal-input-area">
        <Upload
          accept=".py,.js,.ts,.jsx,.tsx,.java,.go,.rs"
          showUploadList={false}
          beforeUpload={handleFileUpload}
        >
          <Button icon={<UploadOutlined />} disabled={isSending} style={{ marginRight: 8, flexShrink: 0 }}>
            上传
          </Button>
        </Upload>
        <Input.TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="（可选）补充说明，例如：重点测试边缘情况..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isSending}
          style={{ flex: 1, resize: "none" }}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={isSending} disabled={!inputValue.trim() && uploadedFiles.length === 0} style={{ marginLeft: 8 }}>
          发送
        </Button>
      </div>
    </>
  );
}
