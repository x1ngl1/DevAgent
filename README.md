# DevAgent - 多智能体协同开发系统

一个基于 **LangChain** 的多智能体协作编程平台。由 4 个 AI Agent（Leader、Coder、PM、Tester）组成虚拟开发团队，实现从需求分析、代码编写、质量审核到测试执行的 **全自动化软件开发流程**。

## ✨ 核心特性

- 🤖 **多 Agent 协作** - 4 个专业角色分工协作，模拟真实开发团队
- 🔄 **DAG 并行执行** - 基于拓扑排序的任务调度，支持依赖管理和并发执行
- 🛠 **工具调用系统** - 8 个内置工具（联网搜索、代码分析、Docker 执行等）
- 📡 **实时通信** - SSE 推送任务进度、Worker 状态、工具调用过程
- 🎯 **人工干预** - 支持 PM 审核环节的实时介入（通过/退回/修改）
- 📦 **一键交付** - 自动生成 ZIP 代码包下载

## 🏗 架构设计

```
用户输入
    ↓
┌─────────────────────────────────┐
│         Leader Agent            │  ← 拆解需求 + 主持讨论
│   (需求分析 → DAG子任务清单)      │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│       团队讨论（最多2轮）         │
│   Coder → PM → Tester → Leader  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│      DAG 并行执行引擎            │
│   Coder → PM → Tester           │  ← PM<60分触发修改循环(最多3轮)
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│      Leader 汇总 + ZIP打包       │
└─────────────────────────────────┘
```

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| **LLM 调用** | LangChain + OpenAI SDK |
| **后端框架** | FastAPI + Uvicorn |
| **数据库** | SQLAlchemy 2.0 + SQLite (aiosqlite) |
| **实时通信** | SSE (Server-Sent Events) |
| **前端框架** | React 18 + Vite |
| **UI 组件** | Ant Design 5 |
| **状态管理** | Zustand |
| **代码执行** | Docker 沙箱 |

## 📁 项目结构

```
Agent/
├── backend/
│   ├── app/
│   │   ├── agents/        # Agent 定义
│   │   │   ├── base.py    # Agent 基类
│   │   │   ├── leader.py  # 团队领导
│   │   │   ├── worker_coder.py   # 程序员
│   │   │   ├── worker_pm.py      # PM 审核
│   │   │   └── worker_tester.py  # 测试工程师
│   │   ├── api/           # API 路由
│   │   ├── models/        # 数据模型
│   │   ├── services/      # 业务服务
│   │   └── utils/         # 工具类
│   │       ├── llm_factory.py     # LLM 调用层（LangChain）
│   │       ├── tool_registry.py   # 工具注册中心
│   │       └── prompt_templates.py # Prompt 模板
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── stores/        # Zustand 状态管理
│   │   └── App.jsx
│   └── package.json
└── README.md
```

## 🚀 快速开始

### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 3. 访问应用

打开浏览器访问 http://localhost:5173

## 🔧 配置说明

### LLM Provider 支持

| Provider | 默认模型 |
|----------|---------|
| DeepSeek | deepseek-v4-flash |
| OpenAI | gpt-4o |
| Anthropic | claude-3-5-sonnet |
| 阿里云通义 | qwen-plus |
| 自定义 | 手动配置 |

每个 Agent 可以独立配置不同的模型和参数。

### 环境变量

```bash
# backend/.env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## 📊 功能演示

### 1. 智能对话
- 自动识别简单问答 vs 编程任务
- 支持联网搜索获取实时信息

### 2. 任务看板
- 实时展示各 Agent 状态
- 子任务进度可视化

### 3. 代码生成
- 自动生成业务代码 + 单元测试 + README
- PM 代码审核（正确性/异常处理/可读性/安全性）

### 4. 人工干预
- PM 审核退回时可选择"通过"、"退回修改"、"我来修改"

## 📝 API 文档

| 接口 | 说明 |
|------|------|
| `POST /api/chat/send` | 智能对话入口 |
| `POST /api/tasks/create` | 创建任务 |
| `GET /api/tasks/history` | 历史任务列表 |
| `GET /api/workers/configs` | Agent 配置 |
| `GET /sse/events` | SSE 实时推送 |

## 🔒 安全说明

- API Key 使用 Fernet 加密存储
- 前端仅显示 Key 后 4 位
- Docker 沙箱隔离代码执行
- 文件读写有目录白名单限制

## 📄 License

MIT License

## 👤 Author

[x1ngl1](https://github.com/x1ngl1)