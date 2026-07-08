import React, { useEffect } from 'react';
import { Layout, App as AntApp, ConfigProvider } from 'antd';
import TopNav from './components/Layout/TopNav';
import TeamBar from './components/Layout/TeamBar';
import StatusBar from './components/Layout/StatusBar';
import ChatArea from './components/Chat/ChatArea';
import KanbanBoard from './components/Kanban/KanbanBoard';
import HistoryPanel from './components/History/HistoryPanel';
import InterventionPanel from './components/Chat/InterventionPanel';
import useWorkerStore from './stores/workerStore';
import useTaskStore from './stores/taskStore';
import { SSE_URL } from './utils/constants';

import '@fontsource/archivo/400.css';
import '@fontsource/archivo/500.css';
import '@fontsource/archivo/600.css';
import '@fontsource/archivo/700.css';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';

import WelcomeModal from './components/WelcomeModal/WelcomeModal';
import './App.css';

const { Content } = Layout;

const theme = {
  token: {
    colorPrimary: '#0891B2',
    colorPrimaryHover: '#0E7490',
    colorPrimaryActive: '#155E75',
    colorPrimaryBg: '#ECFEFF',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#F8FAFC',
    colorBgSpotlight: '#1E293B',
    colorBorder: '#E2E8F0',
    colorBorderSecondary: '#F1F5F9',
    colorText: '#0F172A',
    colorTextSecondary: '#475569',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#CBD5E1',
    colorTextLightSolid: '#FFFFFF',
    colorSuccess: '#059669',
    colorWarning: '#D97706',
    colorError: '#DC2626',
    colorInfo: '#0891B2',
    colorLink: '#0891B2',
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 4,
    fontSize: 13,
    fontFamily: "'DM Sans', -apple-system, sans-serif",
    controlHeight: 32,
    controlHeightSM: 24,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)',
    boxShadowSecondary: '0 4px 12px rgba(0, 0, 0, 0.07)',
  },
};

export default function App() {
  const { message } = AntApp.useApp();
  const { setStatus, addChatMessage, appendStreamToken, finalizeStream, setInterventionRequest, setPaused } = useWorkerStore();

  useEffect(() => {
    const eventSource = new EventSource(SSE_URL);

    eventSource.addEventListener('connected', () => console.log('SSE connected'));

    eventSource.addEventListener('worker_status', (e) => {
      try { const d = JSON.parse(e.data); setStatus(d.worker_id, d.status, d); } catch (_) {}
    });

    eventSource.addEventListener('task_update', (e) => {
      try { const d = JSON.parse(e.data); useTaskStore.getState().setTaskStatus(d.task_id, d.status, d); } catch (_) {}
    });

    eventSource.addEventListener('task_queued', (e) => {
      try { const d = JSON.parse(e.data); useTaskStore.getState().queueTask(d.task_id, d.queue_position); } catch (_) {}
    });

    eventSource.addEventListener('subtask_update', (e) => {
      try { const d = JSON.parse(e.data); useTaskStore.getState().updateSubtask(d.subtask_id, d); } catch (_) {}
    });

    eventSource.addEventListener('chat_message', (e) => {
      try { const d = JSON.parse(e.data); addChatMessage(d); } catch (_) {}
    });

    // 流式token事件
    eventSource.addEventListener('stream_token', (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.token) {
          appendStreamToken(d.worker_id || d.role, d.token);
        }
        if (d.isFinal) {
          finalizeStream(d.worker_id || d.role);
        }
      } catch (_) {}
    });

    // 工具调用进度 — 不发送独立消息，改为更新worker状态细节
    eventSource.addEventListener('tool_call_progress', (e) => {
      try { const d = JSON.parse(e.data);
        if (d.type === 'tool_call_start') {
          // 更新对应 worker 的 detail 字段，不新增聊天消息
          useWorkerStore.getState().setStatus(d.worker_id || 'system', 'running', {
            phase: `工具: ${d.tool_name}`,
          });
        }
      } catch (_) {}
    });

    // 干预请求
    eventSource.addEventListener('intervention_request', (e) => {
      try { const d = JSON.parse(e.data); setInterventionRequest(d); } catch (_) {}
    });

    // 暂停状态
    eventSource.addEventListener('pause_state', (e) => {
      try { const d = JSON.parse(e.data); setPaused(d.paused); useTaskStore.getState().setPaused(d.paused); } catch (_) {}
    });

    // 检查点 — 改为简短的系统提示（不占独立消息气泡）
    eventSource.addEventListener('checkpoint_reached', (e) => {
      try { const d = JSON.parse(e.data);
        useWorkerStore.getState().setStatus('leader', 'running', {
          phase: d.message.slice(0, 40),
        });
      } catch (_) {}
    });

    // 阶段分隔符 — 不加入聊天消息，通过 UI 其他元素展示
    eventSource.addEventListener('phase_separator', () => {});

    eventSource.addEventListener('error', (e) => {
      try { const d = JSON.parse(e.data); message.error(d.error || 'System error'); } catch (_) {}
    });

    eventSource.onerror = () => {};

    return () => eventSource.close();
  }, []);

  return (
    <ConfigProvider theme={theme}>
      <Layout className="app-layout">
        <TopNav />
        <Layout className="main-layout">
          <TeamBar />
          <Content className="terminal-area">
            <ChatArea />
          </Content>
          <Layout.Sider width={260} className="monitor-sider">
            <KanbanBoard />
          </Layout.Sider>
        </Layout>
        <StatusBar />
      </Layout>
      <HistoryPanel />
      <InterventionPanel />
      <WelcomeModal />
    </ConfigProvider>
  );
}