import React, { useState, useEffect } from 'react';
import { Tooltip } from 'antd';
import { SettingOutlined, HistoryOutlined, TrophyOutlined } from '@ant-design/icons';
import useWorkerStore from '../../stores/workerStore';
import useTaskStore from '../../stores/taskStore';
import useExperienceStore from '../../stores/experienceStore';
import SettingsPanel from '../Settings/SettingsPanel';

export default function TopNav() {
  const { workers } = useWorkerStore();
  const { toggleHistory } = useTaskStore();
  const { stats, fetchStats } = useExperienceStore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const activeWorkers = Object.values(workers).filter(w => w.status === 'running').length;
  const totalWorkers = Object.keys(workers).length;

  useEffect(() => { fetchStats(); }, []);

  return (
    <>
      <div className="top-nav">
        <div className="nav-brand">
          <span className="brand-logo">◆</span>
          TEST TEAM
        </div>
        <div className="nav-actions">
          <div className="online-count">
            <span className="online-dot" />
            <span>{activeWorkers}/{totalWorkers}</span>
          </div>
          {stats && stats.total > 0 && (
            <Tooltip title={`经验库: ${stats.total}条 | 推荐: ${stats.recommended}条 | 均分: ${stats.avg_rating}`}>
              <span style={{
                fontSize: 10, color: '#F59E0B', cursor: 'default',
                display: 'flex', alignItems: 'center', gap: 3,
                background: 'rgba(245,158,11,0.12)', padding: '1px 6px', borderRadius: 10,
                border: '1px solid rgba(245,158,11,0.25)',
              }}>
                <TrophyOutlined style={{ fontSize: 10 }} />
                {stats.total}
              </span>
            </Tooltip>
          )}
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
