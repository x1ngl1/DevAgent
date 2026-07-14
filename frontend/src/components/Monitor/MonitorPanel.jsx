import React, { useState } from 'react';
import { Input, Button, Spin } from 'antd';
import { SendOutlined, ClearOutlined } from '@ant-design/icons';
import KanbanBoard from '../Kanban/KanbanBoard';
import useRagStore from '../../stores/ragStore';
import useTaskStore from '../../stores/taskStore';

const { TextArea } = Input;

export default function MonitorPanel() {
  const { taskStatus } = useTaskStore();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="monitor-body" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <KanbanBoard />
      </div>
    </div>
  );
}
