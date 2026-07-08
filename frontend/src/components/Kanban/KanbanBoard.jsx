import React from 'react';
import KanbanColumn from './KanbanColumn';
import ProgressBar from './ProgressBar';
import useTaskStore from '../../stores/taskStore';
import useWorkerStore from '../../stores/workerStore';
import { KANBAN_COLUMNS } from '../../utils/constants';

const ROLE_LABELS = { coder: '程序员', pm: 'PM', tester: '测试', leader: 'Leader' };
const STATUS_ICONS = { pending: '○', running: '●', done: '✓', failed: '✕' };
const STATUS_COLORS = { pending: '#94A3B8', running: '#0891B2', done: '#22C55E', failed: '#EF4444' };

export default function KanbanBoard() {
  const { subtasks, progress, progressText, taskStatus } = useTaskStore();
  const { workers } = useWorkerStore();

  const workerCols = KANBAN_COLUMNS.filter(
    c => c.key !== 'decompose' && c.key !== 'summary'
  );
  const summaryCol = KANBAN_COLUMNS.find(c => c.key === 'summary');
  const decomposeCol = KANBAN_COLUMNS.find(c => c.key === 'decompose');

  return (
    <>
      <div className="monitor-header">
        <span className="monitor-title">执行序列</span>
        <span className="monitor-status">
          {taskStatus === 'running' ? '运行中' : '待命'}
        </span>
      </div>
      <div className="monitor-body">

        {/* ===== 任务拆解 ===== */}
        {subtasks.length > 0 && (
          <div style={{
            padding: '8px 10px',
            marginBottom: 8,
            background: '#F8FAFC',
            borderRadius: 6,
            border: '1px solid #E2E8F0',
          }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: '#64748B',
              textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6,
            }}>
              任务拆解
            </div>
            {subtasks.map((st, i) => {
              const icon = STATUS_ICONS[st.status] || '○';
              const color = STATUS_COLORS[st.status] || '#94A3B8';
              const role = ROLE_LABELS[st.role] || st.role;
              return (
                <div key={st.id || i} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '3px 0 3px ' + (st.depends_on ? 16 : 0) + 'px',
                  fontSize: 12, color: '#334155',
                }}>
                  <span style={{ color, fontSize: 10, flexShrink: 0 }}>{icon}</span>
                  <span style={{
                    fontSize: 10, color: '#64748B', flexShrink: 0,
                    background: '#F1F5F9', padding: '0 5px', borderRadius: 4,
                  }}>{role}</span>
                  <span style={{
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0,
                  }}>{st.description}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* 进度总览 */}
        {subtasks.length > 0 && taskStatus === 'running' && (
          <ProgressBar percent={progress} text={progressText} />
        )}

        {/* 任务拆解区（详细列） */}
        {decomposeCol && subtasks.length > 0 && (
          <>
            <div className="monitor-section">{decomposeCol.title}</div>
            <KanbanColumn column={decomposeCol} subtasks={subtasks} />
          </>
        )}

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
    </>
  );
}
