import React, { useEffect, useState } from 'react';
import { Modal, Spin, Button, Tag } from 'antd';
import { BookOutlined } from '@ant-design/icons';
import { api } from '../../services/api';
import RAGContextDrawer from '../RAG/RAGContextDrawer';

const ROLE_LABELS = { coder: '测试生成', pm: 'PM', tester: '测试执行', leader: 'Leader' };
const STATUS_LABELS = {
  pending: '待执行', running: '执行中', done: '已完成',
  failed: '失败', skipped: '已跳过',
};
const STATUS_COLORS = {
  pending: '#7A7D85', running: '#DDFF28', done: '#22C55E',
  failed: '#EF4444', skipped: '#5A5E65',
};

export default function SubtaskDetailModal({ open, taskId, subtaskId, onClose }) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [ragDrawerOpen, setRagDrawerOpen] = useState(false);

  useEffect(() => {
    if (!open || !subtaskId || !taskId) return;
    setLoading(true);
    setError(null);
    api.get(`/tasks/${taskId}/subtasks/${subtaskId}`)
      .then(r => setDetail(r.data))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [open, subtaskId, taskId]);

  const isCoderDone = detail?.role === 'coder' && detail?.status === 'done';

  return (
    <>
      <Modal
        title={
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            子任务详情
            {detail && <span style={{ fontSize: 11, color: '#7A7D85', marginLeft: 8, fontFamily: "'JetBrains Mono', monospace" }}>{detail.id}</span>}
          </span>
        }
        open={open}
        onCancel={onClose}
        footer={null}
        width={500}
        destroyOnHidden
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <Spin size="small" />
            <div style={{ fontSize: 12, color: '#7A7D85', marginTop: 8 }}>加载中...</div>
          </div>
        ) : error ? (
          <div style={{ padding: 16, color: '#DC2626', fontSize: 12 }}>{error}</div>
        ) : detail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Basic info */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <InfoRow label="角色" value={ROLE_LABELS[detail.role] || detail.role} />
              <InfoRow label="状态" value={STATUS_LABELS[detail.status] || detail.status}
                valueColor={STATUS_COLORS[detail.status]} />
              <InfoRow label="描述" value={detail.description || '-'} span />
              <InfoRow label="依赖" value={detail.depends_on || '无'} />
              {detail.duration > 0 && <InfoRow label="耗时" value={`${detail.duration}s`} />}
            </div>

            {/* RAG 上下文按钮 — 仅对已完成的 Coder 任务显示 */}
            {isCoderDone && (
              <div style={{ margin: '4px 0' }}>
                <Button
                  type="primary"
                  ghost
                  icon={<BookOutlined />}
                  onClick={() => setRagDrawerOpen(true)}
                  size="small"
                  style={{ fontSize: 12 }}
                >
                  查看生成上下文
                </Button>
                <div style={{ fontSize: 10, color: '#7A7D85', marginTop: 4 }}>
                  展示本次生成用到了哪些参考代码和风格特征
                </div>
              </div>
            )}

            {/* Output summary */}
            {detail.output_summary && (
              <>
                <div style={{ height: 1, background: 'rgba(255,255,255,0.08)', margin: '4px 0' }} />
                <div style={{ fontSize: 11, fontWeight: 600, color: '#A8ABB0' }}>
                  执行结果
                </div>
                {typeof detail.output_summary === 'object' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {detail.output_summary.summary && (
                      <div style={{ fontSize: 11, color: '#A8ABB0', lineHeight: 1.5 }}>
                        {detail.output_summary.summary}
                      </div>
                    )}
                    {detail.output_summary.files?.length > 0 && (
                      <div>
                        <div style={{ fontSize: 10, color: '#7A7D85', marginBottom: 4 }}>产出文件：</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {detail.output_summary.files.map(f => (
                            <span key={f} style={{
                              fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
                              color: '#111F26', background: 'rgba(221,255,40,0.15)',
                              padding: '1px 6px', borderRadius: 4,
                            }}>{f}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {detail.output_summary.score != null && (
                      <InfoRow label="PM评分" value={`${detail.output_summary.score}/100`} span />
                    )}
                    {detail.output_summary.issues?.length > 0 && (
                      <div>
                        <div style={{ fontSize: 10, color: '#7A7D85', marginBottom: 4 }}>问题列表：</div>
                        {detail.output_summary.issues.map((issue, i) => (
                          <div key={i} style={{
                            fontSize: 10, color: '#DC2626', padding: '2px 8px',
                            background: '#FEF2F2', borderRadius: 4, marginBottom: 2,
                          }}>{issue}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#A8ABB0', lineHeight: 1.5 }}>
                    {detail.output_summary}
                  </div>
                )}
              </>
            )}

            {/* Error */}
            {detail.error_msg && (
              <div style={{
                fontSize: 10, color: '#DC2626', background: '#FEF2F2',
                padding: '6px 10px', borderRadius: 4, fontFamily: "'JetBrains Mono', monospace",
                wordBreak: 'break-all', lineHeight: 1.5,
              }}>
                {detail.error_msg}
              </div>
            )}
          </div>
        ) : null}
      </Modal>

      {/* RAG 上下文抽屉 */}
      <RAGContextDrawer
        open={ragDrawerOpen}
        taskId={taskId}
        subtaskId={subtaskId}
        onClose={() => setRagDrawerOpen(false)}
      />
    </>
  );
}

function InfoRow({ label, value, valueColor, span }) {
  return (
    <div style={{
      gridColumn: span ? '1 / -1' : undefined,
      display: 'flex', alignItems: 'flex-start', gap: 6,
      fontSize: 11,
    }}>
      <span style={{ color: '#7A7D85', flexShrink: 0, minWidth: 36 }}>{label}</span>
      <span style={{
        color: valueColor || '#A8ABB0',
        fontWeight: valueColor ? 600 : 400,
        wordBreak: 'break-word',
        lineHeight: 1.5,
      }}>{value}</span>
    </div>
  );
}
