import React, { useState } from 'react';
import { Tooltip } from 'antd';
import { SettingOutlined, HistoryOutlined } from '@ant-design/icons';
import useWorkerStore from '../../stores/workerStore';
import useTaskStore from '../../stores/taskStore';
import SettingsPanel from '../Settings/SettingsPanel';

export default function TopNav() {
  const { workers } = useWorkerStore();
  const { toggleHistory } = useTaskStore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const activeWorkers = Object.values(workers).filter(w => w.status === 'running').length;
  const totalWorkers = Object.keys(workers).length;

  return (
    <>
      <div className="top-nav">
        <div className="nav-brand">
          <span className="brand-logo">◆</span>
          AI TEAM
        </div>
        <div className="nav-actions">
          <div className="online-count">
            <span className="online-dot" />
            <span>{activeWorkers}/{totalWorkers}</span>
          </div>
          <Tooltip title="历史任务">
            <HistoryOutlined
              className="nav-btn"
              onClick={toggleHistory}
            />
          </Tooltip>
          <Tooltip title="设置">
            <SettingOutlined
              className="nav-btn"
              onClick={() => setSettingsOpen(true)}
            />
          </Tooltip>
        </div>
      </div>
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </>
  );
}
