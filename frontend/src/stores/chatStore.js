import { create } from 'zustand';
import { api, uploadCodeFile } from '../services/api';
import useWorkerStore from './workerStore';
import useTaskStore from './taskStore';

const useChatStore = create((set, get) => ({
  // 输入框内容
  inputValue: '',

  // 上传的文件列表
  uploadedFiles: [],

  // 发送中状态
  isSending: false,

  // 上传中状态
  isUploading: false,

  // 设置输入
  setInputValue: (value) => set({ inputValue: value }),

  // 添加上传文件
  addUploadedFile: (file) => {
    set((state) => ({
      uploadedFiles: [...state.uploadedFiles, {
        id: `file-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        size: file.size,
        file: file,
        content: '',  // 读取后填充
      }],
    }));
  },

  // 移除上传文件
  removeUploadedFile: (fileId) => {
    set((state) => ({
      uploadedFiles: state.uploadedFiles.filter((f) => f.id !== fileId),
    }));
  },

  // 清空上传文件
  clearUploadedFiles: () => set({ uploadedFiles: [] }),

  // 读取文件内容
  readFileContent: async (fileId) => {
    const file = get().uploadedFiles.find((f) => f.id === fileId);
    if (!file || file.content) return;

    try {
      const text = await file.file.text();
      set((state) => ({
        uploadedFiles: state.uploadedFiles.map((f) =>
          f.id === fileId ? { ...f, content: text } : f
        ),
      }));
      return text;
    } catch (e) {
      console.error('读取文件失败:', e);
      return '';
    }
  },

  // 发送消息（支持文本 + 文件）
  sendMessage: async (userInput) => {
    if (!userInput.trim() && get().uploadedFiles.length === 0) return;

    const { addChatMessage } = useWorkerStore.getState();

    // 如果有上传文件，使用文件上传流程
    const files = get().uploadedFiles;
    if (files.length > 0) {
      set({ isUploading: true });

      // 读取所有文件内容
      for (const f of files) {
        if (!f.content) {
          await get().readFileContent(f.id);
        }
      }

      const updatedFiles = get().uploadedFiles;
      const fileNames = updatedFiles.map((f) => f.name).join(', ');

      // 添加用户消息（显示文件信息）
      addChatMessage({
        role: 'user',
        content: `上传文件: ${fileNames}\n${userInput ? `补充说明: ${userInput}` : '请分析代码并生成测试'}`,
      });

      set({ inputValue: '', isSending: true, isUploading: false });

      try {
        addChatMessage({
          role: 'leader',
          content: `收到文件: ${fileNames}，正在分析代码结构并生成测试...`,
        });

        // 上传文件并获取任务 ID
        const fileToUpload = updatedFiles[0].file;
        const result = await uploadCodeFile(fileToUpload, userInput);
        const taskId = result.task_id;

        if (!taskId) {
          throw new Error('上传响应中缺少 task_id');
        }

        const { createTask } = useTaskStore.getState();
        await createTask(userInput || `测试: ${fileNames}`, taskId, true);
      } catch (error) {
        console.warn('上传失败，使用文本模式回退:', error);
        // 回退：将代码内容作为文本发送
        try {
          const codeContent = updatedFiles.map((f) => f.content).join('\n\n');
          const { createTask } = useTaskStore.getState();
          await createTask(userInput || `测试代码`, null, false, codeContent);
        } catch (fallbackErr) {
          addChatMessage({
            role: 'leader',
            content: `执行失败：${fallbackErr.message || '未知错误'}`,
          });
        }
      } finally {
        set({ isSending: false });
        get().clearUploadedFiles();
      }
      return;
    }

    // 纯文本模式（原有流程）
    addChatMessage({ role: 'user', content: userInput });
    set({ inputValue: '', isSending: true });

    try {
      // 调用 /api/chat/send 做类型判断
      const resp = await api.post('/chat/send', { user_input: userInput });
      const data = resp.data;

      if (data.type === 'direct') {
        addChatMessage({ role: 'leader', content: data.content });
      } else if (data.type === 'task') {
        addChatMessage({
          role: 'leader',
          content: '收到指令！正在拆解任务...',
        });

        const { createTask } = useTaskStore.getState();
        await createTask(userInput, data.task_id);
      }
    } catch (error) {
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
    get().clearUploadedFiles();
  },
}));

export default useChatStore;
