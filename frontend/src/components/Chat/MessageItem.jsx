import React, { useState, useEffect, useRef } from 'react';
import { Button, Modal, message, App } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';

const ROLE_STYLES = {
  user:   { img: '/img/me.png', label: '我', avatarClass: 'avatar-user' },
  leader: { img: '/img/leader.png', label: 'Leader', avatarClass: 'avatar-leader' },
  coder:  { img: '/img/worker.png', label: '程序员', avatarClass: 'avatar-coder' },
  pm:     { img: '/img/pm.png', label: 'PM', avatarClass: 'avatar-pm' },
  tester: { img: '/img/test.png', label: '测试', avatarClass: 'avatar-tester' },
  system: { img: '', label: '系统', avatarClass: 'avatar-system' },
};

export async function downloadZip(zipUrl, suggestedName = 'project.zip', msgApi = null) {
  if (!zipUrl) { (msgApi || message).error('没有可下载的文件'); return; }
  if ('showSaveFilePicker' in window) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        types: [{ description: 'ZIP Archive', accept: { 'application/zip': ['.zip'] } }],
      });
      const writable = await handle.createWritable();
      const response = await fetch(zipUrl);
      const blob = await response.blob();
      await writable.write(blob);
      await writable.close();
      (msgApi || message).success('下载完成');
      return;
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.warn('showSaveFilePicker 失败:', err);
    }
  }
  const a = document.createElement('a');
  a.href = zipUrl;
  a.download = suggestedName;
  a.click();
}

// 打字机效果组件 — 平滑逐字渲染
function TypewriterText({ text, speed = 8, onComplete }) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const indexRef = useRef(0);
  const rafRef = useRef(null);
  const startTimeRef = useRef(0);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);

  useEffect(() => {
    if (!text) { setIsComplete(true); onCompleteRef.current?.(); return; }
    setDisplayedText('');
    setIsComplete(false);
    indexRef.current = 0;
    startTimeRef.current = performance.now();

    const animate = (now) => {
      const elapsed = now - startTimeRef.current;
      const targetIndex = Math.min(Math.floor(elapsed / speed), text.length);
      if (targetIndex > indexRef.current) {
        indexRef.current = targetIndex;
        setDisplayedText(text.slice(0, targetIndex));
      }
      if (indexRef.current < text.length) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setIsComplete(true);
        onCompleteRef.current?.();
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [text, speed]);

  return (
    <span className="typewriter-wrap">
      <span>{displayedText}</span>
      {!isComplete && <span className="typing-cursor" />}
    </span>
  );
}

export default function MessageItem({ message: msg, onComplete }) {
  const { message: messageApi } = App.useApp();
  const role = msg.role || 'system';
  const style = ROLE_STYLES[role] || ROLE_STYLES.system;
  const isUser = role === 'user';
  const [downloadModalOpen, setDownloadModalOpen] = useState(false);
  const [imgError, setImgError] = useState(false);

  const handleDownload = async () => {
    setDownloadModalOpen(false);
    await downloadZip(msg.zipUrl, 'project.zip', messageApi);
  };

  const renderContent = () => {
    if (msg.zipUrl) {
      return (
        <>
          <span>{msg.content}</span>
          <div style={{ marginTop: 10 }}>
            <Button type="primary" size="small" icon={<DownloadOutlined />} onClick={() => setDownloadModalOpen(true)}>
              下载ZIP包
            </Button>
          </div>
          <Modal title="下载确认" open={downloadModalOpen} onOk={handleDownload} onCancel={() => setDownloadModalOpen(false)} okText="选择保存位置" cancelText="取消">
            <p>即将下载项目 ZIP 包。</p>
          </Modal>
        </>
      );
    }
    // 用户消息直接显示，Agent消息使用打字机效果
    if (isUser) {
      return msg.content;
    }
    return <TypewriterText text={msg.content} speed={15} onComplete={onComplete} />;
  };

  return (
    <div className={`message-item ${isUser ? 'message-user' : ''}`}>
      <div className={`message-avatar ${style.avatarClass}`}>
        {style.img && !imgError ? (
          <img
            src={style.img}
            alt={role}
            className="avatar-img"
            onError={() => setImgError(true)}
          />
        ) : (
          <span className="avatar-text">{role === 'user' ? '我' : style.label.slice(0, 2)}</span>
        )}
      </div>
      <div className={`message-bubble ${isUser ? 'message-bubble-user' : ''} bubble-${role}`}>
        {!isUser && <span className="msg-role-tag">{style.label}</span>}
        {renderContent()}
      </div>
    </div>
  );
}
