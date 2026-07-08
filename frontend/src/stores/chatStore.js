import { create } from 'zustand';
import { api } from '../services/api';
import useWorkerStore from './workerStore';
import useTaskStore from './taskStore';

const useChatStore = create((set, get) => ({
  // 输入框内容
  inputValue: '',

  // 发送中状态
  isSending: false,

  // 设置输入
  setInputValue: (value) => set({ inputValue: value }),

  // 发送消息
  sendMessage: async (userInput) => {
    if (!userInput.trim()) return;

    const { addChatMessage } = useWorkerStore.getState();

    // 添加用户消息到聊天
    addChatMessage({ role: 'user', content: userInput });

    set({ inputValue: '', isSending: true });

    try {
      // 先调用 /api/chat/send，让后端判断是问答还是任务
      const resp = await api.post('/chat/send', { user_input: userInput });
      const data = resp.data;

      if (data.type === 'direct') {
        // ✅ 简单问答 — 直接显示回答
        addChatMessage({
          role: 'leader',
          content: data.content,
        });
      } else if (data.type === 'task') {
        // [task] 编程任务 — 走正常任务创建流程
        addChatMessage({
          role: 'leader',
          content: '收到指令！正在拆解任务...',
        });

        const { createTask } = useTaskStore.getState();
        await createTask(userInput, data.task_id);
      }
    } catch (error) {
      // 如果 /api/chat/send 失败，回退到旧的任务创建流程
      console.warn('chat/send 失败，回退到任务模式:', error);

      try {
        addChatMessage({
          role: 'leader',
          content: '收到指令！正在拆解任务...',
        });

        const { createTask } = useTaskStore.getState();
        await createTask(userInput);
      } catch (fallbackErr) {
        addChatMessage({
          role: 'leader',
          content: `执行失败：${fallbackErr.message || '未知错误'}`,
        });
      }
    } finally {
      set({ isSending: false });
    }
  },

  // 清除对话
  clearChat: () => {
    useWorkerStore.getState().resetWorkers();
    useTaskStore.getState().resetTask();
  },
}));

export default useChatStore;
