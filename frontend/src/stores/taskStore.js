import { create } from 'zustand';
import { api } from '../services/api';

const useTaskStore = create((set, get) => ({
  currentTask: null,
  subtasks: [],
  taskStatus: 'idle',
  queuePosition: 0,
  isQueued: false,
  progress: 0,
  progressText: '',
  zipUrl: null,
  taskError: null,
  isPaused: false,

  taskHistory: [],
  historyLoading: false,
  historyOpen: false,
  historyDetail: null,
  historyDetailLoading: false,

  createTask: async (userInput, existingTaskId = null, isFileUpload = false, codeContent = '') => {
    try {
      set({ taskStatus: 'running', taskError: null, zipUrl: null, subtasks: [], queuePosition: 0, isQueued: false, isPaused: false });
      let task_id;
      if (existingTaskId) {
        task_id = existingTaskId;
        set({ currentTask: { id: task_id, userInput }, taskStatus: 'queued' });
      } else if (codeContent) {
        // 代码内容直接提交（使用专用端点）
        const response = await api.post('/tasks/create-with-code', {
          user_input: userInput,
          code_content: codeContent,
        });
        task_id = response.data.task_id;
        set({ currentTask: { id: task_id, userInput }, taskStatus: response.data.status || 'queued' });
      } else {
        const response = await api.post('/tasks/create', { user_input: userInput });
        task_id = response.data.task_id;
        set({ currentTask: { id: task_id, userInput }, taskStatus: response.data.status || 'queued' });
      }
      return task_id;
    } catch (error) {
      const errMsg = error.response?.data?.detail || error.message || 'Task creation failed';
      set({ taskStatus: 'failed', taskError: errMsg });
      throw error;
    }
  },

  setTaskStatus: (taskId, status, data = {}) => {
    const state = get();
    // 兼容 SSE 事件在 createTask 之前到达的情况
    if (state.currentTask && state.currentTask.id !== taskId) return;
    const clearQueue = status === 'running';
    const updates = {
      taskStatus: status,
      zipUrl: data.zip_url || state.zipUrl,
      taskError: data.error || null,
      isQueued: clearQueue ? false : state.isQueued,
      queuePosition: clearQueue ? 0 : state.queuePosition,
    };
    // 如果 currentTask 未设置但收到 running 事件，先建立 currentTask
    if (!state.currentTask && (status === 'running' || status === 'queued')) {
      updates.currentTask = { id: taskId, userInput: '' };
    }
    set(updates);
  },

  queueTask: (taskId, position) => {
    const state = get();
    if (state.currentTask && state.currentTask.id !== taskId) return;
    const updates = { isQueued: true, queuePosition: position, taskStatus: 'queued' };
    if (!state.currentTask) {
      updates.currentTask = { id: taskId, userInput: '' };
    }
    set(updates);
  },

  updateSubtask: (subtaskId, data) => {
    set((state) => {
      // Normalize depends_on to array
      const normalized = { ...data };
      if (normalized.depends_on != null && !Array.isArray(normalized.depends_on)) {
        normalized.depends_on = [normalized.depends_on];
      }
      const existing = state.subtasks.find(s => s.id === subtaskId);
      if (existing) {
        return { subtasks: state.subtasks.map(s => s.id === subtaskId ? { ...s, ...normalized } : s) };
      }
      return { subtasks: [...state.subtasks, { id: subtaskId, ...normalized }] };
    });
  },

  updateProgress: () => {
    const { subtasks } = get();
    if (subtasks.length === 0) { set({ progress: 0, progressText: '' }); return; }
    const done = subtasks.filter(s => s.status === 'done' || s.status === 'failed').length;
    const pct = Math.round((done / subtasks.length) * 100);
    set({ progress: pct, progressText: `${pct}% ${done}/${subtasks.length} 完成` });
  },

  // 暂停/恢复
  setPaused: (isPaused) => set({ isPaused }),

  pauseTask: async () => {
    try { await api.post('/tasks/pause'); set({ isPaused: true }); return true; }
    catch (e) { console.error('Pause failed:', e); return false; }
  },

  resumeTask: async () => {
    try { await api.post('/tasks/resume'); set({ isPaused: false }); return true; }
    catch (e) { console.error('Resume failed:', e); return false; }
  },

  // 干预响应
  sendIntervention: async (requestId, decision, feedback = '') => {
    try {
      await api.post('/tasks/intervention', { request_id: requestId, decision, feedback });
      return true;
    } catch (e) { console.error('Intervention failed:', e); return false; }
  },

  // 历史任务
  toggleHistory: () => {
    const { historyOpen } = get();
    if (!historyOpen) get().fetchHistory();
    set({ historyOpen: !historyOpen, historyDetail: null });
  },

  closeHistory: () => set({ historyOpen: false, historyDetail: null }),

  fetchHistory: async () => {
    set({ historyLoading: true });
    try { const r = await api.get('/tasks/history?limit=50'); set({ taskHistory: r.data.tasks || [] }); }
    catch (e) { console.error('Fetch history failed:', e); }
    finally { set({ historyLoading: false }); }
  },

  fetchTaskDetail: async (taskId) => {
    set({ historyDetailLoading: true, historyDetail: null });
    try { const r = await api.get(`/tasks/${taskId}`); set({ historyDetail: r.data }); }
    catch (e) { console.error('Fetch detail failed:', e); }
    finally { set({ historyDetailLoading: false }); }
  },

  deleteTask: async (taskId) => {
    try { await api.delete(`/tasks/${taskId}`);
      set(s => ({ taskHistory: s.taskHistory.filter(t => t.id !== taskId), historyDetail: s.historyDetail?.id === taskId ? null : s.historyDetail })); return true; }
    catch (e) { console.error('Delete failed:', e); return false; }
  },

  batchDeleteTask: async (taskIds) => {
    try { const r = await api.post('/tasks/batch/delete', taskIds);
      set(s => ({ taskHistory: s.taskHistory.filter(t => !taskIds.includes(t.id)), historyDetail: taskIds.includes(s.historyDetail?.id) ? null : s.historyDetail })); return r.data; }
    catch (e) { console.error('Batch delete failed:', e); return null; }
  },

  resetTask: () => {
    set({
      currentTask: null, subtasks: [], taskStatus: 'idle', progress: 0, progressText: '',
      zipUrl: null, taskError: null, queuePosition: 0, isQueued: false, isPaused: false,
    });
  },
}));

export default useTaskStore;