/* 常量定义 */

// Worker角色定义
export const WORKER_ROLES = {
  leader: { label: 'Leader', icon: '/img/leader.png', description: '副官/调度' },
  coder: { label: '程序员', icon: '/img/worker.png', description: '代码编写/README' },
  pm: { label: 'PM Agent', icon: '/img/pm.png', description: '质量审核/决策' },
  tester: { label: '测试工程师', icon: '/img/test.png', description: '单元测试/覆盖率' },
};

// 状态颜色映射
export const STATUS_COLORS = {
  pending: '#d9d9d9',
  running: '#faad14',
  done: '#52c41a',
  failed: '#ff4d4f',
  disabled: '#d9d9d9',
};

// 状态图标映射
export const STATUS_ICONS = {
  pending: '○',
  running: '●',
  done: '✓',
  failed: '✕',
  disabled: '⊘',
};

// 状态中文映射
export const STATUS_LABELS = {
  pending: '待执行',
  running: '执行中',
  done: '已完成',
  failed: '失败',
  disabled: '已禁用',
};

// 任务状态颜色
export const TASK_STATUS_COLORS = {
  pending: 'default',
  running: 'processing',
  done: 'success',
  failed: 'error',
};

// 看板列定义
export const KANBAN_COLUMNS = [
  { key: 'decompose', title: '任务拆解', width: '20%' },
  { key: 'coder', title: '程序员', width: '20%' },
  { key: 'pm', title: 'PM审核', width: '20%' },
  { key: 'tester', title: '测试', width: '20%' },
  { key: 'summary', title: '汇总', width: '20%' },
];

// 预设LLM提供商
export const LLM_PROVIDERS = [
  {
    key: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-v4-flash', 'deepseek-v4'],
  },
  {
    key: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  },
  {
    key: 'anthropic',
    label: 'Anthropic',
    baseUrl: 'https://api.anthropic.com/v1',
    models: ['claude-3-5-sonnet', 'claude-3-opus'],
  },
  {
    key: 'aliyun',
    label: '通义千问(阿里云)',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-max', 'qwen-turbo', 'glm-5', 'glm-5-plus'],
    _aliases: ['qwen'],
  },
  {
    key: 'custom',
    label: '自定义',
    baseUrl: '',
    models: [],
  },
];

// API基础路径
export const API_BASE = '/api';

// SSE相关
export const SSE_URL = `${import.meta.env.VITE_SSE_URL || '/sse'}/events`;
