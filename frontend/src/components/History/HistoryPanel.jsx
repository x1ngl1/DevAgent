import React, { useState } from 'react';
import { Button, Spin, Empty, Tag, Modal, Checkbox, App } from 'antd';
import { CloseOutlined, RightOutlined, DownOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons';
import useTaskStore from '../../stores/taskStore';

const statusConfig = {
  done: { color: 'success', label: '完成' },
  failed: { color: 'error', label: '失败' },
  running: { color: 'processing', label: '执行中' },
  queued: { color: 'warning', label: '排队中' },
  pending: { color: 'default', label: '等待中' },
};

export default function HistoryPanel() {
  const { message, modal } = App.useApp();
  const {
    taskHistory, historyLoading,
    historyOpen, historyDetail, historyDetailLoading,
    closeHistory, fetchTaskDetail, deleteTask, batchDeleteTask,
  } = useTaskStore();

  const [expandedId, setExpandedId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [batchDeleting, setBatchDeleting] = useState(false);

  const handleToggleDetail = (taskId) => {
    if (expandedId === taskId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(taskId);
    fetchTaskDetail(taskId);
  };

  const handleDelete = (taskId, e) => {
    e.stopPropagation();
    modal.confirm({
      title: '确认删除',
      content: `确定要删除任务 ${taskId} 吗？此操作不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setDeletingId(taskId);
        const success = await deleteTask(taskId);
        setDeletingId(null);
        if (success) {
          message.success(`任务 ${taskId} 已删除`);
          if (expandedId === taskId) setExpandedId(null);
          setSelectedIds(prev => prev.filter(id => id !== taskId));
        } else {
          message.error('删除失败，请重试');
        }
      },
    });
  };

  const toggleSelect = (taskId, e) => {
    e.stopPropagation();
    setSelectedIds(prev =>
      prev.includes(taskId)
        ? prev.filter(id => id !== taskId)
        : [...prev, taskId]
    );
  };

  const toggleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedIds(taskHistory.map(t => t.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleBatchDelete = () => {
    modal.confirm({
      title: '确认批量删除',
      content: `确定要删除选中的 ${selectedIds.length} 个任务吗？此操作不可恢复。`,
      okText: '批量删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBatchDeleting(true);
        const result = await batchDeleteTask(selectedIds);
        setBatchDeleting(false);
        if (result) {
          message.success(`成功删除 ${result.deleted_count} 个任务`);
          if (result.errors?.length > 0) {
            message.warning(`有 ${result.errors.length} 个任务删除失败`);
          }
          setSelectedIds([]);
          if (selectedIds.includes(expandedId)) setExpandedId(null);
        } else {
          message.error('批量删除失败，请重试');
        }
      },
    });
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  if (!historyOpen) return null;

  return (
    <div className="history-overlay" onClick={closeHistory}>
      <div className="history-panel" onClick={(e) => e.stopPropagation()}>
        <div className="history-panel-header">
          <span className="history-panel-title">历史任务</span>
          {selectedIds.length > 0 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                已选 {selectedIds.length} 项
              </span>
              <Button
                type="danger"
                size="small"
                icon={<DeleteOutlined />}
                loading={batchDeleting}
                onClick={handleBatchDelete}
              >
                批量删除
              </Button>
            </div>
          )}
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={closeHistory}
            style={{ color: 'var(--color-text-tertiary)' }}
          />
        </div>

        <div className="history-panel-body">
          {historyLoading ? (
            <div className="history-loading">
              <Spin size="small" />
              <span>加载中...</span>
            </div>
          ) : taskHistory.length === 0 ? (
            <Empty
              description="暂无历史任务"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ marginTop: 60 }}
            />
          ) : (
            <div className="history-list">
              {/* 全选行 */}
              <div className="history-item" style={{ padding: '6px 12px', borderBottom: '1px solid var(--color-border)' }}>
                <Checkbox
                  checked={selectedIds.length === taskHistory.length && taskHistory.length > 0}
                  indeterminate={selectedIds.length > 0 && selectedIds.length < taskHistory.length}
                  onChange={toggleSelectAll}
                  style={{ fontSize: 12 }}
                >
                  全选
                </Checkbox>
              </div>
              {taskHistory.map((task) => {
                const cfg = statusConfig[task.status] || statusConfig.pending;

                return (
                  <div key={task.id} className="history-item">
                    <div className="history-item-header"
                      onClick={() => handleToggleDetail(task.id)}
                    >
                      <div className="history-item-left">
                        <Checkbox
                          checked={selectedIds.includes(task.id)}
                          onChange={(e) => toggleSelect(task.id, e)}
                          style={{ marginRight: 8 }}
                        />
                        <span className="history-item-id">{task.id}</span>
                        <Tag color={cfg.color} style={{ fontSize: 10, lineHeight: '18px', padding: '0 6px' }}>
                          {cfg.label}
                        </Tag>
                      </div>
                      <div className="history-item-right">
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          loading={deletingId === task.id}
                          onClick={(e) => handleDelete(task.id, e)}
                          style={{ fontSize: 12, width: 24, height: 24, minWidth: 24, marginRight: 4 }}
                        />
                        <span className="history-item-time">{formatTime(task.created_at)}</span>
                        {expandedId === task.id ? (
                          <DownOutlined style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }} />
                        ) : (
                          <RightOutlined style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }} />
                        )}
                      </div>
                    </div>

                    <div className="history-item-input">
                      {task.user_input?.length > 80
                        ? task.user_input.slice(0, 80) + '...'
                        : task.user_input || '(无描述)'
                      }
                    </div>

                    {/* 展开详情 */}
                    {expandedId === task.id && (
                      <div className="history-item-detail">
                        {historyDetailLoading ? (
                          <div className="history-loading" style={{ padding: '12px 0' }}>
                            <Spin size="small" />
                          </div>
                        ) : historyDetail && historyDetail.id === task.id ? (
                          <>
                            {/* 子任务列表 */}
                            {historyDetail.subtasks?.length > 0 && (
                              <div className="history-subtasks">
                                <div className="history-subtask-title">子任务</div>
                                {historyDetail.subtasks.map((st) => (
                                  <div key={st.id} className="history-subtask">
                                    <span className="hs-id">{st.id}</span>
                                    <span className="hs-role">{st.role}</span>
                                    <span className="hs-desc">{st.description || '—'}</span>
                                    <Tag
                                      color={statusConfig[st.status]?.color || 'default'}
                                      style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px', marginLeft: 'auto', flexShrink: 0 }}
                                    >
                                      {statusConfig[st.status]?.label || st.status}
                                    </Tag>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* 时间信息 */}
                            <div className="history-meta">
                              <div className="history-meta-row">
                                <span className="history-meta-label">创建时间</span>
                                <span className="history-meta-value">{formatTime(historyDetail.created_at)}</span>
                              </div>
                              {historyDetail.finished_at && (
                                <div className="history-meta-row">
                                  <span className="history-meta-label">完成时间</span>
                                  <span className="history-meta-value">{formatTime(historyDetail.finished_at)}</span>
                                </div>
                              )}
                            </div>

                            {/* 下载 */}
                            {task.status === 'done' && task.zip_url && (
                              <div style={{ marginTop: 8 }}>
                                <Button
                                  type="primary"
                                  size="small"
                                  icon={<DownloadOutlined />}
                                  href={task.zip_url}
                                  target="_blank"
                                  block
                                >
                                  下载 ZIP
                                </Button>
                              </div>
                            )}
                          </>
                        ) : null}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
