import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Spin, Tag } from 'antd';
import { SendOutlined, ClearOutlined, CloseOutlined, BookOutlined, FileTextOutlined } from '@ant-design/icons';
import useRagStore from '../../stores/ragStore';

const { TextArea } = Input;

export default function RAGPanel() {
  const {
    messages, isAsking, stats, panelOpen,
    ask, closePanel, clearMessages, fetchStats,
  } = useRagStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isAsking) return;
    ask(input);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!panelOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      width: 380,
      height: '100vh',
      background: '#FFFFFF',
      borderLeft: '1px solid rgba(255,255,255,0.08)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 1050,
      boxShadow: '-4px 0 24px rgba(0,0,0,0.08)',
      animation: 'slideInRight 0.2s ease-out',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BookOutlined style={{ fontSize: 15, color: '#DDFF28' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0' }}>知识问答</span>
          {stats && (
            <span style={{ fontSize: 10, color: '#7A7D85', background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 8 }}>
              {stats.count} 条知识
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Button type="text" size="small" icon={<ClearOutlined />}
            onClick={clearMessages} style={{ fontSize: 11, color: '#A8ABB0' }} />
          <Button type="text" size="small" icon={<CloseOutlined />}
            onClick={closePanel} style={{ fontSize: 11, color: '#A8ABB0' }} />
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: 12,
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {messages.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', flex: 1, gap: 8,
            color: '#7A7D85', fontSize: 12, textAlign: 'center', padding: 24,
          }}>
            <FileTextOutlined style={{ fontSize: 28, opacity: 0.3 }} />
            <div>向知识库提问</div>
            <div style={{ fontSize: 10, color: '#CBD5E1', maxWidth: 240 }}>
              输入与项目代码、历史任务相关的问题，系统会检索知识库后给出回答
            </div>
            {stats && stats.count > 0 && (
              <div style={{ fontSize: 10, color: '#CBD5E1', marginTop: 4 }}>
                知识库现有 {stats.count} 条记录
                {stats.sources && Object.entries(stats.sources).map(([k, v]) => (
                  <span key={k} style={{ marginLeft: 4 }}>| {k}: {v}</span>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} style={{
              display: 'flex', flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              animation: 'msgFadeIn 0.2s ease-out',
            }}>
              <div style={{
                maxWidth: '85%',
                padding: '8px 12px',
                borderRadius: 8,
                fontSize: 12,
                lineHeight: 1.6,
                background: msg.role === 'user' ? '#DDFF28' : 'rgba(255,255,255,0.04)',
                color: msg.role === 'user' ? '#FFFFFF' : msg.isError ? '#EF4444' : '#7A7D85',
                border: msg.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.08)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {msg.content}
              </div>
              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div style={{
                  marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 3,
                  maxWidth: '85%',
                }}>
                  {msg.sources.map((src, i) => (
                    <Tag key={i} style={{
                      fontSize: 9, lineHeight: '16px', margin: 0,
                      fontFamily: "'JetBrains Mono', monospace",
                    }} color="cyan">
                      {src.source}
                      {src.relevance ? ` (${(src.relevance * 100).toFixed(0)}%)` : ''}
                    </Tag>
                  ))}
                </div>
              )}
              {msg.fromCache && (
                <div style={{ fontSize: 9, color: '#7A7D85', marginTop: 2 }}>
                  来自缓存
                </div>
              )}
            </div>
          ))
        )}
        {isAsking && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
            color: '#7A7D85', fontSize: 12,
          }}>
            <Spin size="small" />
            <span>检索知识库...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0, display: 'flex', gap: 6,
      }}>
        <TextArea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题..."
          autoSize={{ minRows: 1, maxRows: 3 }}
          style={{ flex: 1, fontSize: 12, resize: 'none' }}
          disabled={isAsking}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={isAsking}
          disabled={!input.trim()}
          style={{ alignSelf: 'flex-end' }}
        />
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes msgFadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
