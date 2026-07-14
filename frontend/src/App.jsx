import React, { useEffect } from 'react';
import { Layout, App as AntApp, ConfigProvider } from 'antd';
import TopNav from './components/Layout/TopNav';
import TeamBar from './components/Layout/TeamBar';
import StatusBar from './components/Layout/StatusBar';
import ChatArea from './components/Chat/ChatArea';
import MonitorPanel from './components/Monitor/MonitorPanel';
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
    colorPrimary: '#DDFF28',
    colorPrimaryHover: '#C0E000',
    colorPrimaryActive: '#A8CC00',
    colorPrimaryBg: 'rgba(221,255,40,0.1)',
    colorBgContainer: '#1A2A33',
    colorBgElevated: '#1E2B35',
    colorBgLayout: '#111F26',
    colorBgSpotlight: '#0E1A20',
    colorBorder: 'rgba(122,125,133,0.15)',
    colorBorderSecondary: 'rgba(122,125,133,0.08)',
    colorText: '#F7F7F5',
    colorTextSecondary: '#A8ABB0',
    colorTextTertiary: '#7A7D85',
    colorTextQuaternary: '#5A5E65',
    colorTextLightSolid: '#111F26',
    colorSuccess: '#22C55E',
    colorWarning: '#F59E0B',
    colorError: '#EF4444',
    colorInfo: '#00E5FF',
    colorLink: '#00E5FF',
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 4,
    fontSize: 13,
    fontFamily: "'DM Sans', -apple-system, sans-serif",
    controlHeight: 32,
    controlHeightSM: 24,
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    boxShadowSecondary: '0 8px 24px rgba(0,0,0,0.5)',
  },
};

export default function App() {
  const { message } = AntApp.useApp();
  const { setStatus, addChatMessage, appendStreamToken, finalizeStream, setInterventionRequest, setPaused } = useWorkerStore();

  useEffect(() => {
    let eventSource = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_DELAY = 30000; // 30秒上限

    function connectSSE() {
      if (eventSource) {
        eventSource.close();
      }

      eventSource = new EventSource(SSE_URL);

      eventSource.addEventListener('connected', () => {
        console.log('SSE connected');
        reconnectAttempts = 0; // 重置重连计数
      });

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
        try {
          const d = JSON.parse(e.data);
          useTaskStore.getState().updateSubtask(d.subtask_id, d);
          useTaskStore.getState().updateProgress();
        } catch (_) {}
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

      // 工具调用进度
      eventSource.addEventListener('tool_call_progress', (e) => {
        try { const d = JSON.parse(e.data);
          const wid = d.worker_id || 'system';
          if (d.type === 'tool_call_start') {
            useWorkerStore.getState().setStatus(wid, 'running', {
              phase: `工具: ${d.tool_name}`,
            });
            useWorkerStore.getState().addToolCallLog(wid, {
              tool_name: d.tool_name,
              args: d.args ? JSON.stringify(d.args).slice(0, 60) : '',
              status: 'running',
            });
          } else if (d.type === 'tool_call_end') {
            useWorkerStore.getState().addToolCallLog(wid, {
              tool_name: d.tool_name,
              result: d.result ? String(d.result).slice(0, 60) : '',
              status: 'done',
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

      // 检查点
      eventSource.addEventListener('checkpoint_reached', (e) => {
        try { const d = JSON.parse(e.data);
          useWorkerStore.getState().setStatus('leader', 'running', {
            phase: d.message.slice(0, 40),
          });
        } catch (_) {}
      });

      // 阶段分隔符
      eventSource.addEventListener('phase_separator', () => {});

      eventSource.addEventListener('error', (e) => {
        try { const d = JSON.parse(e.data); message.error(d.error || 'System error'); } catch (_) {}
      });

      eventSource.onerror = (err) => {
        console.warn('SSE 连接断开，正在重连...', err);
        eventSource.close();

        // 指数退避重连
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
        reconnectAttempts++;
        console.log(`SSE 将在 ${delay}ms 后重连 (第 ${reconnectAttempts} 次)`);

        reconnectTimer = setTimeout(() => {
          connectSSE();
        }, delay);
      };
    }

    // 初始连接
    connectSSE();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
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
            <MonitorPanel />
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