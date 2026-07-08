import React from 'react';
import useTaskStore from '../../stores/taskStore';
import useWorkerStore from '../../stores/workerStore';

export default function StatusBar() {
  const { currentTask, taskStatus, progress } = useTaskStore();
  const { workers } = useWorkerStore();

  const activeWorkers = Object.values(workers).filter(w => w.status === 'running').length;

  const statusLabel = {
    idle: '待命',
    running: '执行中',
    done: '已完成',
    failed: '失败',
  };

  return (
    <div className="status-bar">
      <div className="sb-item">
        <span className="sb-label">TASK</span>
        <span className="sb-value">
          {currentTask ? currentTask.id : '——'}
        </span>
      </div>
      <div className="sb-item">
        <span className="sb-label">STATUS</span>
        <span className="sb-value">
          {taskStatus ? statusLabel[taskStatus] || taskStatus : '待命'}
        </span>
      </div>
      {activeWorkers > 0 && (
        <div className="sb-item">
          <span className="sb-label">WORKERS</span>
          <span className="sb-value">{activeWorkers} 执行中</span>
        </div>
      )}
      {taskStatus === 'running' && progress > 0 && (
        <div className="sb-progress">
          <div className="sb-progress-bar">
            <div
              className="sb-progress-fill"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
