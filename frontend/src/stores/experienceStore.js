import { create } from 'zustand';
import { api } from '../services/api';

const useExperienceStore = create((set, get) => ({
  // Current task rating state
  currentTaskId: null,
  rating: 0,
  tags: '',
  notes: '',
  savedExp: null,
  saving: false,
  // Search/recommended
  recommended: [],
  searchResults: [],
  stats: null,
  loading: false,

  reset: () => set({
    currentTaskId: null, rating: 0, tags: '', notes: '',
    savedExp: null, saving: false,
  }),

  setRating: (rating) => set({ rating }),
  setTags: (tags) => set({ tags }),
  setNotes: (notes) => set({ notes }),

  save: async (taskData) => {
    const { currentTaskId, rating, tags, notes } = get();
    if (!currentTaskId && !taskData?.task_id) return;

    set({ saving: true });
    try {
      const res = await api.post('/experience/save', {
        task_id: currentTaskId || taskData.task_id,
        user_input: taskData?.user_input || '',
        summary: taskData?.summary || '',
        rating: rating || 0,
        tags: tags || '',
        notes: notes || '',
        task_status: taskData?.task_status || 'done',
        subtask_count: taskData?.subtask_count || 0,
        total_duration: taskData?.total_duration || 0,
      });
      set({ savedExp: res.data, saving: false });
      // Refresh stats
      get().fetchStats();
      return res.data;
    } catch (e) {
      set({ saving: false });
      throw e;
    }
  },

  fetchRecommended: async () => {
    try {
      const res = await api.get('/experience/recommended', { params: { limit: 5 } });
      set({ recommended: res.data.results || [] });
    } catch (_) {}
  },

  search: async (q) => {
    set({ loading: true });
    try {
      const res = await api.get('/experience/search', { params: { q, limit: 10 } });
      set({ searchResults: res.data.results || [], loading: false });
    } catch (_) {
      set({ loading: false });
    }
  },

  fetchStats: async () => {
    try {
      const res = await api.get('/experience/stats');
      set({ stats: res.data });
    } catch (_) {}
  },
}));

export default useExperienceStore;
