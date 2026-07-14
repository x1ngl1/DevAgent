"""RAG API routes - knowledge Q&A + subtask context endpoint"""
import re
import json
import logging
import ast
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])

# Pydantic models
class AskRequest(BaseModel):
    question: str
    k: int = 5

class AddKnowledgeRequest(BaseModel):
    text: str
    source: str = "manual"
    task_id: str = ""


def get_rag():
    from app.main import app_state
    if not app_state.rag_service:
        raise HTTPException(503, "RAG service not available")
    return app_state.rag_service


@router.post("/ask")
async def ask_question(req: AskRequest, rag=Depends(get_rag)):
    """Ask a question to the knowledge base"""
    if not req.question or not req.question.strip():
        raise HTTPException(400, "Question is required")
    result = await rag.answer_question(req.question.strip(), k=req.k)
    return result


@router.get("/stats")
async def get_stats(rag=Depends(get_rag)):
    """Get knowledge base statistics"""
    return rag.get_knowledge_stats()


@router.post("/knowledge")
async def add_knowledge(req: AddKnowledgeRequest, rag=Depends(get_rag)):
    """Add a document to the knowledge base manually"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "Text is required")
    meta = {"source": req.source, "type": "manual"}
    if req.task_id:
        meta["task_id"] = req.task_id
    ok = rag.add_document(req.text.strip(), meta)
    if ok:
        return {"status": "added", "stats": rag.get_knowledge_stats()}
    return {"status": "skipped (already exists or empty)", "stats": rag.get_knowledge_stats()}


@router.post("/cache/clear")
async def clear_cache(rag=Depends(get_rag)):
    """Clear the response cache"""
    rag.clear_cache()
    return {"status": "cleared"}


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str, rag=Depends(get_rag)):
    """Delete a document by ID"""
    ok = rag.delete_document(doc_id)
    return {"status": "deleted" if ok else "not_found"}


# ── 新增：获取子任务的 RAG 上下文 ──

@router.get("/subtask-context/{task_id}/{subtask_id}")
async def get_subtask_context(task_id: str, subtask_id: str, rag=Depends(get_rag)):
    """获取某次 Coder 生成测试时的 RAG 上下文（相似代码、依赖文档、风格特征）"""
    from app.main import app_state
    from app.models.task import Subtask
    from sqlalchemy import select

    db = app_state.db_session
    if not db:
        raise HTTPException(503, "Database not available")

    # 1. 从 DB 加载 subtask
    async with db() as s:
        st = await s.get(Subtask, subtask_id)
        if not st:
            raise HTTPException(404, "Subtask not found")

        description = st.description or ""
        output_summary_raw = st.output_summary or "{}"

    # 2. 解析 output_summary 提取函数名
    function_name = ""
    code_content = ""
    if isinstance(output_summary_raw, str):
        try:
            parsed = json.loads(output_summary_raw)
        except json.JSONDecodeError:
            parsed = {}
    else:
        parsed = output_summary_raw

    files = parsed.get("files", [])
    summary_text = parsed.get("summary", "")

    # 从 description 提取函数名（格式: "为函数 xxx 编写单元测试"）
    func_match = re.search(r"函数\s*([\w_]+)", description)
    if func_match:
        function_name = func_match.group(1)
    if not function_name and summary_text:
        func_match = re.search(r"为\s*([\w_]+)\s*生成", summary_text)
        if func_match:
            function_name = func_match.group(1)
    if not function_name:
        # 尝试从任务描述中的函数签名提取
        sig_match = re.search(r"def\s+(\w+)\s*\(", description)
        if sig_match:
            function_name = sig_match.group(1)

    # 3. 查询 RAG 知识库获取相似代码片段
    reference_context = []
    if function_name:
        # 用函数名 + 代码特征查询
        query_text = function_name
        if summary_text:
            query_text = f"{function_name} {summary_text[:100]}"
        docs = rag.query(query_text, k=3)
        for doc in docs:
            reference_context.append({
                "text": doc.get("text", "")[:500],
                "source": doc.get("metadata", {}).get("source", "knowledge_base"),
                "relevance": round(1 - doc.get("distance", 0), 3),
                "metadata": doc.get("metadata", {}),
            })

    # 4. 从被测代码提取风格特征
    style_features = {
        "naming_convention": "snake_case",
        "exceptions": [],
        "decorators": [],
        "imports": [],
    }

    # 如果有文件内容（代码片段），做 AST 分析
    all_code_text = " ".join(files)
    # 尝试从 RAG 检索到的代码中提取特征
    for ctx in reference_context:
        code_text = ctx.get("text", "")
        if code_text:
            try:
                tree = ast.parse(code_text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            lib = alias.name.split(".")[0]
                            if lib not in style_features["imports"]:
                                style_features["imports"].append(lib)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            lib = node.module.split(".")[0]
                            if lib not in style_features["imports"]:
                                style_features["imports"].append(lib)
                    elif isinstance(node, (ast.Raise,)):
                        if isinstance(node, ast.Raise) and hasattr(node, 'exc') and node.exc:
                            if isinstance(node.exc, ast.Call) and hasattr(node.exc.func, 'id'):
                                exc_name = node.exc.func.id
                                if exc_name not in style_features["exceptions"]:
                                    style_features["exceptions"].append(exc_name)
                    elif isinstance(node, ast.FunctionDef):
                        for deco in node.decorator_list:
                            if hasattr(deco, 'id') and deco.id not in style_features["decorators"]:
                                style_features["decorators"].append(deco.id)
                            elif hasattr(deco, 'attr'):
                                deco_name = f"{deco.value.id}.{deco.attr}" if hasattr(deco, 'value') and hasattr(deco.value, 'id') else deco.attr
                                if deco_name not in style_features["decorators"]:
                                    style_features["decorators"].append(deco_name)
                        # 推断命名规范
                        if node.name and node.name[0].isupper():
                            style_features["naming_convention"] = "PascalCase"
                        elif "_" in node.name:
                            style_features["naming_convention"] = "snake_case"
                        else:
                            style_features["naming_convention"] = "camelCase"
            except SyntaxError:
                pass

    # 5. 依赖文档摘要
    known_libs = {
        "pytest": "Python 官方单元测试框架，支持 fixture、parametrize、mock 等特性",
        "unittest": "Python 内置单元测试框架",
        "mock": "Python 模拟对象库，用于隔离外部依赖",
        "requests": "HTTP 请求库",
        "flask": "轻量级 Python Web 框架",
        "fastapi": "高性能 Python Web 框架",
        "sqlalchemy": "Python SQL 工具包和 ORM",
        "numpy": "Python 数值计算库",
        "pandas": "Python 数据分析库",
        "django": "Python Web 框架",
        "pytest-cov": "pytest 覆盖率插件，生成 coverage.xml 报告",
        "pytest-mock": "pytest 的 mock 插件",
    }
    dependency_docs = []
    for imp in style_features["imports"]:
        if imp in known_libs:
            dependency_docs.append({"library": imp, "usage": known_libs[imp]})
    if "pytest" not in [d["library"] for d in dependency_docs]:
        dependency_docs.insert(0, {"library": "pytest", "usage": known_libs["pytest"]})
    if "pytest-cov" not in [d["library"] for d in dependency_docs]:
        dependency_docs.append({"library": "pytest-cov", "usage": known_libs["pytest-cov"]})

    return {
        "function_name": function_name or "未知函数",
        "reference_context": reference_context,
        "dependency_docs": dependency_docs,
        "style_features": style_features,
        "subtask_info": {
            "role": st.role if st else "coder",
            "status": st.status if st else "done",
            "description": description[:200] if description else "",
            "files": files,
        },
    }


# ── Admin-only endpoints (no UI) ──

@router.post("/inject-history")
async def inject_history(rag=Depends(get_rag)):
    """Inject all historical completed tasks into the RAG knowledge base.
    Admin only - call via curl / httpie, no frontend UI.
    """
    from sqlalchemy import select
    from app.main import app_state

    db = app_state.db_session
    if not db:
        raise HTTPException(503, "Database not available")

    async with db() as s:
        from app.models.task import Task, Subtask
        from sqlalchemy.orm import selectinload

        tasks = (await s.execute(
            select(Task)
            .options(selectinload(Task.subtasks))
            .where(Task.status == "done")
            .order_by(Task.created_at)
        )).scalars().all()

        if not tasks:
            return {"status": "no tasks to inject", "count": 0}

        injected = 0
        skipped = 0
        errors = 0
        for t in tasks:
            try:
                subtask_rows = []
                for st in t.subtasks:
                    subtask_rows.append({
                        "id": st.id,
                        "role": st.role,
                        "description": st.description,
                        "output_summary": st.output_summary or "",
                    })

                task_data = {
                    "id": t.id,
                    "user_input": t.user_input or "",
                    "subtasks": subtask_rows,
                }

                ok = rag.add_task_result(task_data)
                if ok:
                    injected += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Inject task {t.id} failed: {e}")
                errors += 1

        stats = rag.get_knowledge_stats()
        return {
            "status": "done",
            "total_tasks": len(tasks),
            "injected": injected,
            "skipped": skipped,
            "errors": errors,
            "knowledge_stats": stats,
        }
