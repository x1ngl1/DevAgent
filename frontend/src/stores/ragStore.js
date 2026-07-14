import { create } from 'zustand';
import { api } from '../services/api';

const useRagStore = create((set, get) => ({
  // Panel state
  panelOpen: false,
  // Messages
  messages: [],
  isAsking: false,
  // Knowledge stats
  stats: null,
  statsLoading: false,
  // Error
  error: null,

  togglePanel: () => {
    const { panelOpen } = get();
    if (!panelOpen) get().fetchStats();
    set({ panelOpen: !panelOpen });
  },

  openPanel: () => {
    set({ panelOpen: true });
    get().fetchStats();
  },

  closePanel: () => set({ panelOpen: false, error: null }),

  ask: async (question) => {
    if (!question.trim()) return;

    const userMsg = { role: 'user', content: question, id: 'q_' + Date.now() };
    set(state => ({
      messages: [...state.messages, userMsg],
      isAsking: true,
      error: null,
    }));

    try {
      const res = await api.post('/rag/ask', { question: question.trim(), k: 5 });
      const data = res.data;
      const assistantMsg = {
        role: 'assistant',
        content: data.answer || '无回答',
        sources: data.sources || [],
        id: 'a_' + Date.now(),
        fromCache: data.from_cache,
      };
      set(state => ({
        messages: [...state.messages, assistantMsg],
        isAsking: false,
      }));
    } catch (e) {
      const errMsg = e.response?.data?.detail || e.message || '请求失败';
      set(state => ({
        messages: [...state.messages, {
          role: 'assistant',
          content: `回答失败: ${errMsg}`,
          id: 'err_' + Date.now(),
          isError: true,
        }],
        isAsking: false,
        error: errMsg,
      }));
    }
  },

  fetchStats: async () => {
    set({ statsLoading: true });
    try {
      const res = await api.get('/rag/stats');
      set({ stats: res.data, statsLoading: false });
    } catch (e) {
      set({ statsLoading: false });
    }
  },

  clearMessages: () => set({ messages: [], error: null }),

  // ── 新增：获取子任务的 RAG 上下文（用于看板抽屉）──
  subtaskContext: null,
  subtaskContextLoading: false,
  subtaskContextError: null,

  fetchSubtaskContext: async (taskId, subtaskId) => {
    set({ subtaskContextLoading: true, subtaskContext: null, subtaskContextError: null });
    try {
      const res = await api.get(`/rag/subtask-context/${taskId}/${subtaskId}`);
      set({ subtaskContext: res.data, subtaskContextLoading: false });
      return res.data;
    } catch (e) {
      const errMsg = e.response?.data?.detail || e.message || '获取上下文失败';
      set({ subtaskContextError: errMsg, subtaskContextLoading: false });
      return null;
    }
  },

  clearSubtaskContext: () => set({ subtaskContext: null, subtaskContextError: null }),
}));

export default useRagStore;
