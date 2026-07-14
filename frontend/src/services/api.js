import axios from 'axios';
import { API_BASE } from '../utils/constants';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API请求失败:', error);
    return Promise.reject(error);
  }
);

// 上传代码文件并创建测试任务
export async function uploadCodeFile(file, supplement = '') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('supplement', supplement);
  const response = await api.post('/tasks/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return response.data;
}

// 提交代码文本（粘贴模式）
export async function submitCodeText(code, supplement = '', filename = 'code.py') {
  const response = await api.post('/tasks/upload/text', {
    code,
    supplement,
    filename,
  });
  return response.data;
}

export default api;
