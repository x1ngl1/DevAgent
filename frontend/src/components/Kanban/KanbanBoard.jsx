import React, { useState } from 'react';
import KanbanColumn from './KanbanColumn';
import DAGView from './DAGView';
import SubtaskDetailModal from './SubtaskDetailModal';
import ProgressBar from './ProgressBar';
import TaskRating from '../Experience/TaskRating';
import useTaskStore from '../../stores/taskStore';
import useWorkerStore from '../../stores/workerStore';
import useExperienceStore from '../../stores/experienceStore';
import { KANBAN_COLUMNS } from '../../utils/constants';

const ROLE_LABELS = { coder: '程序员', pm: 'PM', tester: '测试', leader: 'Leader' };
const STATUS_ICONS = { pending: '○', running: '●', done: '✓', failed: '✕' };
const STATUS_COLORS = { pending: '#7A7D85', running: '#DDFF28', done: '#22C55E', failed: '#EF4444' };

export default function KanbanBoard({ hideHeader }) {
  const { subtasks, progress, progressText, taskStatus, currentTask } = useTaskStore();
  const { workers } = useWorkerStore();
  const [detailModal, setDetailModal] = useState({ open: false, subtaskId: null });

  const workerCols = KANBAN_COLUMNS.filter(
    c => c.key !== 'decompose' && c.key !== 'summary'
  );
  const summaryCol = KANBAN_COLUMNS.find(c => c.key === 'summary');

  const handleNodeClick = (subtaskId) => {
    setDetailModal({ open: true, subtaskId });
  };

  const handleCloseDetail = () => {
    setDetailModal({ open: false, subtaskId: null });
  };

  return (
    <>
      {!hideHeader && (
        <div className="monitor-header">
          <span className="monitor-title">执行序列</span>
          <span className="monitor-status">
            {taskStatus === 'running' ? '运行中' : taskStatus === 'done' ? '完成' : '待命'}
          </span>
        </div>
      )}
      <div className="monitor-body">

        {/* ===== DAG 任务依赖图 ===== */}
        {subtasks.length > 0 && (
          <div style={{
            background: '#FFFFFF',
            borderRadius: 8,
            border: '1px solid #E2E8F0',
            marginBottom: 4,
          }}>
            <DAGView subtasks={subtasks} onNodeClick={handleNodeClick} />
          </div>
        )}

        {/* 进度总览 */}
        {subtasks.length > 0 && taskStatus === 'running' && (
          <ProgressBar percent={progress} text={progressText} />
        )}

        {/* 任务完成评分 */}
        <TaskRating />

        {/* Worker 列 */}
        {workerCols.map((col) => {
          const workerState = workers[col.key] || { status: 'idle' };
          return (
            <React.Fragment key={col.key}>
              <div className="monitor-section">
                <span>{col.title}</span>
              </div>
              <KanbanColumn
                column={col}
                workerState={workerState}
                subtasks={subtasks}
              />
            </React.Fragment>
          );
        })}

        {/* 汇总 */}
        {summaryCol && (
          <>
            <div className="monitor-section">{summaryCol.title}</div>
            <KanbanColumn
              column={summaryCol}
              subtasks={subtasks}
            />
          </>
        )}

      </div>

      {/* 子任务详情弹窗 */}
      <SubtaskDetailModal
        open={detailModal.open}
        taskId={currentTask?.id}
        subtaskId={detailModal.subtaskId}
        onClose={handleCloseDetail}
      />
    </>
  );
}
