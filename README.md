多智能体遗留代码测试生成系统

上传遗留代码文件，系统自动分析函数结构，生成单元测试，执行测试并输出覆盖率报告和重构建议。
演示地址：http://39.106.210.254

工作流程：
用户上传 .py 或 .js/.ts 代码文件。
Leader Agent 扫描文件，识别所有函数签名，构建函数调用依赖图，按被调用次数排序生成测试任务队列。
Coder Agent 按任务队列依次生成单元测试，覆盖正常路径、边界值、空值和异常情况。
Tester Agent 在 Docker 沙箱中执行测试，解析 pytest 输出的覆盖率数据。
PM Agent 对测试结果进行评分。硬指标占70分，其中pytest通过率40分，行覆盖率30分。软指标占30分，评估断言有效性和代码可读性。总分低于80分时驳回并附修改意见。
平均单次任务耗时3分钟。

后端启动：
cd backend
pip install -r requirements.txt
cp .env.example .env
编辑 .env 填入 LLM API Key
uvicorn app.main:app --reload --port 8000

前端启动：
cd frontend
npm install
npm run dev
访问 http://localhost:5173


实测数据：
使用三个开源工具类文件进行测试，均为0覆盖率初始状态。
Flask登录模块，180行，生成测试后覆盖率82%，耗时2分40秒。
数据处理工具类，220行，生成测试后覆盖率91%，耗时3分10秒。
带自定义异常的模块，95行，生成测试后覆盖率78%，耗时2分10秒。
覆盖率受代码复杂度和LLM响应速度影响。

技术栈：
后端：Python 3.11、FastAPI、SQLAlchemy、SQLite
LLM调用：LangChain、OpenAI SDK，支持DeepSeek、通义、Claude切换
实时推送：SSE
前端：React 18、Vite、Ant Design 5、Zustand
代码执行：Docker沙箱


支持的LLM Provider：
DeepSeek、OpenAI、Anthropic、阿里云通义、自定义配置。每个Agent可独立配置模型和参数。

