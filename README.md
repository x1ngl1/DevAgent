# 多智能体遗留代码测试生成系统

> 基于 LangChain 的多智能体测试生成平台，由 4 个 AI Agent 组成虚拟测试团队，自动分析遗留代码结构、生成单元测试、计算覆盖率并给出重构建议。

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| LLM 调用 | LangChain + OpenAI SDK |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 + SQLite |
| 实时通信 | SSE Server-Sent Events |
| 前端 | React 18 + Vite + Ant Design 5 + Zustand |
| 代码执行 | Docker 沙箱 |

## 核心功能

| 功能 | 描述 |
|------|------|
| 代码结构分析 | 上传 .py/.js/.ts 等代码文件，自动识别函数/类签名，构建调用关系 DAG |
| 智能测试生成 | 基于依赖图按优先级生成单元测试，覆盖正常路径、边界值、异常情况、空值处理 |
| 混合评分体系 | 硬指标（pytest 通过率 40 分 + 覆盖率 30 分）+ 软指标（断言质量 30 分） |
| 覆盖率报告 | 自动运行测试并解析 coverage.xml，输出行覆盖率和分支覆盖率 |
| 圈复杂度分析 | 识别高复杂度函数，给出重构建议 |
| DAG 并行执行 | 基于拓扑排序的任务调度引擎，核心函数优先测试 |
| 实时通信 | 13 种 SSE 事件类型推送测试进度、覆盖率数据、Agent 状态 |

## 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 项目结构

```
Agent/
├── backend/
│   ├── app/
│   │   ├── agents/          # Leader Coder PM Tester 四个角色
│   │   ├── api/             # FastAPI 路由（含文件上传端点）
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── services/        # DAG 执行器、任务服务、评价器
│   │   │   ├── evaluator.py     # 覆盖率解析 + 圈复杂度计算
│   │   │   ├── sandbox.py       # Docker 沙箱测试执行
│   │   │   └── task_service.py  # 任务编排引擎
│   │   └── utils/           # LLM 调用层、提示词模板
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React 组件（含文件上传）
│   │   └── stores/          # Zustand 状态管理
│   └── package.json
└── README.md
```

## 使用方式

```
┌─────────────────────────────────────────────────────────────┐
│  1. 上传代码  →  2. AI分析  →  3. 生成测试  →  4. 执行评分  │
└─────────────────────────────────────────────────────────────┘
```

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 上传代码文件 | 点击上传按钮选择 .py/.js/.ts 文件 |
| 2 | 补充说明（可选） | 在文本框输入重点关注的方向 |
| 3 | 自动分析 | 系统自动识别函数结构，按重要性排序生成测试任务 |
| 4 | 测试生成 | AI 团队并行生成各函数的单元测试 |
| 5 | 测试执行 | 在 Docker 沙箱中运行测试并收集覆盖率 |
| 6 | 综合评分 | PM 按硬指标+软指标混合评分 |
| 7 | 输出报告 | 包含覆盖率数据、测试结果、重构建议 |

## API 接口

| 方法 | 路径 | 说明 |
|:----:|------|------|
| `POST` | `/api/tasks/upload` | 上传代码文件并创建测试任务 |
| `POST` | `/api/tasks/upload/text` | 提交代码文本创建测试任务 |
| `POST` | `/api/tasks/create` | 创建测试任务（支持代码内容） |
| `GET` | `/api/tasks/history` | 历史任务列表 |
| `POST` | `/api/chat/send` | 智能对话入口 |
| `GET` | `/sse/events` | SSE 实时推送 |

## 验收测试

| 编号 | 验收项 | 验收方法 |
|:----:|--------|----------|
| A1 | 上传 .py 文件识别所有函数并输出测试任务清单 | 上传 `sample.py` 检查 DAG 任务列表 |
| A2 | 生成的测试代码可通过 pytest 执行，无语法错误 | 运行 `pytest --tb=short` |
| A3 | PM 评分中硬指标占比≥70%，输出结构化评分报告 | 检查返回 JSON 含 `score` 字段 |
| A4 | 前端输入区已改为文件上传模式 | 界面截图验证 |
| A5 | 对同一段代码连续运行 3 次，覆盖率波动 ≤ 5% | 记录 3 次覆盖率数据 |

## 支持的 LLM Provider

- DeepSeek
- OpenAI
- Anthropic
- 阿里云通义
- 自定义配置

> 每个 Agent 可独立配置不同模型和参数。

## 仓库地址

https://github.com/x1ngl1/-
