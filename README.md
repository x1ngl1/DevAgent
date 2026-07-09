DevAgent 多智能体协同开发系统

基于 LangChain 的多智能体协作编程平台，由 4 个 AI Agent 组成虚拟开发团队，自动完成需求分析、代码编写、质量审核、测试执行，输出可运行的代码包。

技术栈
- LLM 调用：LangChain + OpenAI SDK
- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.0 + SQLite
- 实时通信：SSE Server-Sent Events
- 前端：React 18 + Vite + Ant Design 5 + Zustand
- 代码执行：Docker 沙箱

核心功能
- 多 Agent 协作：Leader 拆解需求，Coder 编写代码，PM 审核质量，Tester 执行测试，模拟真实开发团队流程
- DAG 并行执行：基于拓扑排序的任务调度引擎，支持依赖管理和并发执行，PM 审核不合格自动触发修改循环最多 3 轮
- 工具调用系统：8 个内置工具包括联网搜索、代码分析、文件读写、Docker 执行，Agent 可自主判断何时调用
- 实时通信：13 种 SSE 事件类型推送任务进度、Worker 状态、工具调用过程，前端实时展示看板和打字机效果
- 人工干预：PM 审核环节支持用户实时介入，可选择通过、退回修改或我来修改

快速启动

后端：
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

项目结构
```
Agent/
├── backend/
│   ├── app/
│   │   ├── agents/        Leader Coder PM Tester 四个角色
│   │   ├── api/           FastAPI 路由
│   │   ├── models/        SQLAlchemy 数据模型
│   │   ├── services/      DAG 执行器 任务服务
│   │   └── utils/         LLM 调用层 工具注册
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    React 组件
│   │   └── stores/        Zustand 状态管理
│   └── package.json
└── README.md
```

支持的 LLM Provider
DeepSeek OpenAI Anthropic 阿里云通义 自定义配置

每个 Agent 可独立配置不同模型和参数。

API 接口
POST /api/chat/send           智能对话入口
POST /api/tasks/create        创建任务
GET  /api/tasks/history       历史任务列表
GET  /api/workers/configs     Agent 配置
GET  /sse/events              SSE 实时推送

安全说明
API Key 使用 Fernet 加密存储，前端仅显示后 4 位
Docker 沙箱隔离代码执行，内存 512MB CPU 50% 超时 30 秒
文件读写有目录白名单限制

仓库地址
https://github.com/x1ngl1/-