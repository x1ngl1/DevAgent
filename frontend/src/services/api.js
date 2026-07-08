import axios from 'axios';
import { API_BASE } from '../utils/constants';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
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

export default api;
