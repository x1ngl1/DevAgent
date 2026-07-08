import axios from 'axios';

const api = axios.create({
  baseURL: '/api',  // 关键：统一添加 /api 前缀
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
