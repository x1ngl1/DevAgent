import React, { useState } from 'react';
import { Button, Modal, message } from 'antd';
import { DownloadOutlined, EyeOutlined, ToolOutlined } from '@ant-design/icons';
import { STATUS_LABELS } from '../../utils/constants';
import useTaskStore from '../../stores/taskStore';
import useWorkerStore from '../../stores/workerStore';

async function downloadZip(zipUrl, suggestedName = 'project.zip') {
  if (!zipUrl) {
    message.error('没有可下载的文件');
    return;
  }
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
      message.success('下载完成');
      return;
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.warn('showSaveFilePicker 失败，使用传统下载:', err);
    }
  }
  const a = document.createElement('a');
  a.href = zipUrl;
  a.download = suggestedName;
  a.click();
}

export default function KanbanColumn({ column, workerState, subtasks }) {
  const { key, title } = column;
  const { zipUrl } = useTaskStore();
  const toolCallLogs = useWorkerStore((s) => s.toolCallLogs[key] || []);
  const streamMsg = useWorkerStore((s) => s.streamingMessages[key]);
  const [downloadModalOpen, setDownloadModalOpen] = useState(false);
  const [detailModal, setDetailModal] = useState({ open: false, title: '', content: '' });

  const handleDownloadClick = () => setDownloadModalOpen(true);
  const handleDownloadConfirm = async () => {
    setDownloadModalOpen(false);
    await downloadZip(zipUrl, 'project.zip');
  };

  // ── 任务拆解列 ──
  if (key === 'decompose') {
    if (subtasks.length === 0) return null;

    return (
      <div className="subtask-list">
        {subtasks.map((st) => {
          const label = STATUS_LABELS[st.status] || '待执行';
          return (
            <div key={st.id} className="monitor-subtask">
              <span className="st-id">{st.id}</span>
              <span className="st-desc">{st.description || st.role || '-'}</span>
              <span className="st-tag">{label}</span>
            </div>
          );
        })}
      </div>
    );
  }

  // ── 汇总列 ──
  if (key === 'summary') {
    const doneCount = subtasks.filter(s => s.status === 'done').length;
    const totalCount = subtasks.length;

    return (
      <div className="monitor-card">
        <div className="mc-header">
          <span className="mc-title">汇总</span>
          {totalCount > 0 && (
            <span className="mc-status">
              {doneCount === totalCount ? '完成' : '进行中'}
            </span>
          )}
        </div>
        {totalCount > 0 && (
          <>
            <div className="mc-row">
              <span className="mc-label">进度</span>
              <span className="mc-value">{doneCount}/{totalCount}</span>
            </div>
            <div className="monitor-progress">
              <div className="mp-bar">
                <div className="mp-fill" style={{ width: `${(doneCount / totalCount) * 100}%` }} />
              </div>
              <div className="mp-text">{Math.round((doneCount / totalCount) * 100)}%</div>
            </div>
          </>
        )}
        {doneCount === totalCount && totalCount > 0 && zipUrl && (
          <div style={{ marginTop: 8 }}>
            <Button type="primary" size="small" block icon={<DownloadOutlined />} onClick={handleDownloadClick}>
              下载 ZIP
            </Button>
          </div>
        )}

        <Modal
          title="下载确认"
          open={downloadModalOpen}
          onOk={handleDownloadConfirm}
          onCancel={() => setDownloadModalOpen(false)}
          okText="选择保存位置"
          cancelText="取消"
        >
          <p>即将下载项目 ZIP 包。</p>
          <p>点击"选择保存位置"后，将弹出系统文件选择窗口。</p>
          <p style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>
            注：部分浏览器不支持选择保存位置，将使用默认下载目录。
          </p>
        </Modal>
      </div>
    );
  }

  // ── Worker 列（coder / pm / tester）──
  const state = workerState || { status: 'idle' };
  const statusLabel = STATUS_LABELS[state.status] || '空闲';
  const statusClass = state.status === 'running' ? 'running'
    : state.status === 'done' ? 'done'
    : state.status === 'failed' || state.status === 'error' ? 'failed'
    : '';
  const hasNoTask = state.status === 'idle' && !state.phase;

  if (hasNoTask) {
    return (
      <div className="monitor-card" style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 12, padding: '12px 8px' }}>
        等待任务...
      </div>
    );
  }

  return (
    <div className="monitor-card">
      <div className="mc-header">
        <span className="mc-title">{title}</span>
        <span className={`mc-status ${statusClass}`}>{statusLabel}</span>
      </div>

      {/* 程序员列 */}
      {key === 'coder' && (
        <>
          {state.phase && (
            <div className="mc-row">
              <span className="mc-label">阶段</span>
              <span className="mc-value">{state.phase}</span>
            </div>
          )}
          {state.duration > 0 && (
            <div className="mc-row">
              <span className="mc-label">耗时</span>
              <span className="mc-value">{state.duration}s</span>
            </div>
          )}
          {state.files && state.files.length > 0 && (
            <div className="mc-row">
              <span className="mc-label">产出</span>
              <span className="mc-value" style={{ fontSize: 10 }}>{state.files.join(', ')}</span>
            </div>
          )}
          {state.detail && (
            <div className="mc-detail">{state.detail}</div>
          )}
          {state.status === 'done' && state.files?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              <Button type="link" size="small" icon={<DownloadOutlined />} style={{ padding: 0 }} onClick={handleDownloadClick}>
                下载
              </Button>
            </div>
          )}
        </>
      )}

      {/* PM 审核列 */}
      {key === 'pm' && (
        <>
          {state.phase && (
            <div className="mc-row">
              <span className="mc-label">阶段</span>
              <span className="mc-value">{state.phase}</span>
            </div>
          )}
          {state.duration > 0 && (
            <div className="mc-row">
              <span className="mc-label">耗时</span>
              <span className="mc-value">{state.duration}s</span>
            </div>
          )}
          {state.score !== null && (
            <div className="mc-row">
              <span className="mc-label">评分</span>
              <span className="mc-value" style={{ fontWeight: 600 }}>{state.score}分</span>
            </div>
          )}
          {state.decision && (
            <div className="mc-row">
              <span className="mc-label">结论</span>
              <span className="mc-value">
                {state.decision === 'pass' ? '通过' : state.decision === 'pass_with_warning' ? '放行' : '退回'}
              </span>
            </div>
          )}
          {state.detail && (
            <div style={{ marginTop: 6 }}>
              <Button type="link" size="small" icon={<EyeOutlined />} style={{ padding: 0 }}
                onClick={() => setDetailModal({ open: true, title: '审核详情', content: state.detail })}>
                查看详情
              </Button>
            </div>
          )}
        </>
      )}

      {/* 测试列 */}
      {key === 'tester' && (
        <>
          {state.phase && (
            <div className="mc-row">
              <span className="mc-label">阶段</span>
              <span className="mc-value">{state.phase}</span>
            </div>
          )}
          {state.duration > 0 && (
            <div className="mc-row">
              <span className="mc-label">耗时</span>
              <span className="mc-value">{state.duration}s</span>
            </div>
          )}
          {state.coverage !== null && (
            <div className="mc-row">
              <span className="mc-label">覆盖率</span>
              <span className="mc-value" style={{ fontWeight: 600 }}>
                {(state.coverage * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {state.testFiles && state.testFiles.length > 0 && (
            <div className="mc-row">
              <span className="mc-label">文件</span>
              <span className="mc-value" style={{ fontSize: 10 }}>{state.testFiles.join(', ')}</span>
            </div>
          )}
          {state.detail && (
            <div style={{ marginTop: 6 }}>
              <Button type="link" size="small" icon={<EyeOutlined />} style={{ padding: 0 }}
                onClick={() => setDetailModal({ open: true, title: '测试报告', content: state.detail })}>
                查看报告
              </Button>
            </div>
          )}
        </>
      )}

      {/* 工具调用日志（运行时显示） */}
      {toolCallLogs.length > 0 && state.status === 'running' && (
        <div style={{ marginTop: 6, borderTop: '1px solid var(--color-border)', paddingTop: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--color-text-tertiary)', marginBottom: 2 }}>
            <ToolOutlined style={{ marginRight: 2 }} />工具调用
          </div>
          {toolCallLogs.slice(0, 3).map((log, i) => (
            <div key={i} style={{ fontSize: 8, color: 'var(--color-text-tertiary)', lineHeight: 1.6, paddingLeft: 4 }}>
              {log.status === 'running' ? (
                <span className="tool-call-running">▶</span>
              ) : (
                <span style={{ color: '#52c41a' }}>✓</span>
              )}
              {' '}{log.tool_name}
              {log.args && <span style={{ color: '#7A7D85' }}> {log.args}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Agent 实时思考过程 */}
      {state.status === 'running' && streamMsg?.isStreaming && streamMsg?.content && (
        <div style={{
          marginTop: 6,
          padding: '4px 6px',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 4,
          fontSize: 8,
          lineHeight: 1.5,
          color: '#A8ABB0',
          maxHeight: 40,
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          {streamMsg.content}
        </div>
      )}

      {/* 详情弹窗 */}
      <Modal
        title={detailModal.title}
        open={detailModal.open}
        onCancel={() => setDetailModal({ open: false, title: '', content: '' })}
        footer={<Button type="primary" onClick={() => setDetailModal({ open: false, title: '', content: '' })}>关闭</Button>}
      >
        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13, lineHeight: 1.6, margin: 0 }}>
          {detailModal.content}
        </pre>
      </Modal>

      <Modal
        title="下载确认"
        open={downloadModalOpen}
        onOk={handleDownloadConfirm}
        onCancel={() => setDownloadModalOpen(false)}
        okText="选择保存位置"
        cancelText="取消"
      >
        <p>即将下载项目 ZIP 包。</p>
        <p>点击"选择保存位置"后，将弹出系统文件选择窗口。</p>
        <p style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>
          注：部分浏览器不支持选择保存位置，将使用默认下载目录。
        </p>
      </Modal>
    </div>
  );
}
