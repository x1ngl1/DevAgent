import { create } from 'zustand';
import { api } from '../services/api';

let _msgIdCounter = 0;
const nextMsgId = () => `${Date.now()}-${++_msgIdCounter}`;

const defaultWorkerStates = {
  leader: { status: 'idle', phase: '', duration: 0, detail: '' },
  coder: { status: 'idle', phase: '', duration: 0, detail: '', files: [], test_scenarios: [] },
  pm: { status: 'idle', phase: '', duration: 0, detail: '', score: null, decision: '', hard_score: null, soft_score: null },
  tester: { status: 'idle', phase: '', duration: 0, detail: '', coverage: null, coverage_detail: null, testFiles: [], test_counts: null },
};

const useWorkerStore = create((set, get) => ({
  workers: { ...JSON.parse(JSON.stringify(defaultWorkerStates)) },
  configs: {},
  configUpdatedAt: null,   // 用于右侧面板同步的更新时间戳
  chatMessages: [],
  streamingMessages: {},    // { worker_id: { content: string, isStreaming: bool } }
  interventionRequest: null, // { request_id, type, context } or null
  isPaused: false,
  toolCallLogs: {}, // { worker_id: [{tool_name, timestamp, status}] }

  setStatus: (workerId, status, data = {}) => {
    set((state) => ({
      workers: {
        ...state.workers,
        [workerId]: {
          ...state.workers[workerId],
          status,
          phase: data.phase || state.workers[workerId].phase,
          duration: data.duration || state.workers[workerId].duration,
          detail: data.summary || data.error || state.workers[workerId].detail,
          ...(data.files ? { files: data.files } : {}),
          ...(data.score ? { score: data.score } : {}),
          ...(data.decision ? { decision: data.decision } : {}),
          ...(data.coverage ? { coverage: data.coverage } : {}),
          ...(data.coverage_detail ? { coverage_detail: data.coverage_detail } : {}),
          ...(data.test_files ? { testFiles: data.test_files } : {}),
          ...(data.test_counts ? { test_counts: data.test_counts } : {}),
          ...(data.hard_score ? { hard_score: data.hard_score } : {}),
          ...(data.soft_score ? { soft_score: data.soft_score } : {}),
          ...(data.test_scenarios ? { test_scenarios: data.test_scenarios } : {}),
        },
      },
    }));
  },

  addToolCallLog: (workerId, logEntry) => {
    set((state) => {
      const logs = state.toolCallLogs[workerId] || [];
      logs.unshift({ ...logEntry, timestamp: new Date().toLocaleTimeString() });
      if (logs.length > 5) logs.pop();
      return { toolCallLogs: { ...state.toolCallLogs, [workerId]: logs } };
    });
  },

  addChatMessage: (data) => {
    set((state) => ({
      chatMessages: [
        ...state.chatMessages,
        {
          id: nextMsgId(),
          role: data.role || 'system',
          content: data.content || '',
          zipUrl: data.zip_url || null,
          phase: data.phase || 'execution',
          timestamp: new Date().toLocaleTimeString(),
        },
      ],
    }));
  },

  // 流式token处理：追加到当前流消息中
  appendStreamToken: (workerId, token) => {
    set((state) => {
      const current = state.streamingMessages[workerId] || { content: '', isStreaming: true };
      const newContent = current.content + token;
      // 如果还没有流式消息，创建一条
      if (!state.streamingMessages[workerId]) {
        return {
          streamingMessages: {
            ...state.streamingMessages,
            [workerId]: { content: newContent, isStreaming: true },
          },
        };
      }
      return {
        streamingMessages: {
          ...state.streamingMessages,
          [workerId]: { content: newContent, isStreaming: true },
        },
      };
    });
  },

  // 流式完成：将流消息转为正式聊天消息
  finalizeStream: (workerId) => {
    set((state) => {
      const streamMsg = state.streamingMessages[workerId];
      if (!streamMsg || !streamMsg.content) return state;
      
      const newMessages = [
        ...state.chatMessages,
        {
          id: nextMsgId(),
          role: workerId,
          content: streamMsg.content,
          phase: 'execution',
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
      const newStreaming = { ...state.streamingMessages };
      delete newStreaming[workerId];
      return { chatMessages: newMessages, streamingMessages: newStreaming };
    });
  },

  // 干预请求
  setInterventionRequest: (request) => {
    set({ interventionRequest: request });
  },

  clearInterventionRequest: () => {
    set({ interventionRequest: null });
  },

  // 暂停状态
  setPaused: (isPaused) => {
    set({ isPaused });
  },

  resetWorkers: () => {
    set({
      workers: { ...JSON.parse(JSON.stringify(defaultWorkerStates)) },
      chatMessages: [],
      streamingMessages: {},
      interventionRequest: null,
      isPaused: false,
    });
  },

  loadConfigs: async () => {
    try {
      const response = await api.get('/configs');
      const configMap = {};
      for (const cfg of response.data.configs) {
        configMap[cfg.worker_id] = cfg;
      }
      set({ configs: configMap, configUpdatedAt: Date.now() });
      return configMap;
    } catch (error) {
      console.error('Load configs failed:', error);
      return {};
    }
  },

  saveConfig: async (workerId, config) => {
    try {
      await api.put(`/configs/${workerId}`, config);
      set({ configUpdatedAt: Date.now() });
      return true;
    } catch (error) {
      console.error('Save config failed:', error);
      return false;
    }
  },

  resetConfigs: async () => {
    try {
      await api.post('/configs/reset');
      set({ configUpdatedAt: Date.now() });
      return true;
    } catch (error) {
      console.error('Reset configs failed:', error);
      return false;
    }
  },
}));

export default useWorkerStore;