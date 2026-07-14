"""RAG Service - lightweight retrieval-augmented generation with Chroma + SiliconFlow embeddings"""
import os
import json
import logging
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Chroma & LangChain
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage

from app.utils.llm_factory import LLMFactory

RAG_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_data")
CHROMA_DIR = os.path.join(RAG_DATA_DIR, "chroma")
COLLECTION_NAME = "knowledge_base"
CACHE_SIZE = 100
CACHE_SIMILARITY_THRESHOLD = 0.95
TOP_K_DEFAULT = 5
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Default embedding config (SiliconFlow compatible)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


class RAGService:
    def __init__(self, llm_config: Optional[Dict] = None):
        self.llm_config = llm_config or {}
        self._collection = None
        self._cache = {}  # question_hash -> (answer, sources)

        # Ensure data dir exists
        os.makedirs(CHROMA_DIR, exist_ok=True)

        # Init embedding
        try:
            self._embeddings = OpenAIEmbeddings(
                model=EMBEDDING_MODEL,
                api_key=EMBEDDING_API_KEY or "not-needed",
                base_url=EMBEDDING_BASE_URL,
            )
            logger.info(f"RAG embedding initialized: {EMBEDDING_MODEL} @ {EMBEDDING_BASE_URL}")
        except Exception as e:
            logger.warning(f"Embedding init failed (will retry on first use): {e}")
            self._embeddings = None

        # Init Chroma
        try:
            self._client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            # Get or create collection
            try:
                self._collection = self._client.get_collection(COLLECTION_NAME)
                logger.info(f"Loaded existing Chroma collection '{COLLECTION_NAME}' ({self._collection.count()} docs)")
            except Exception:
                self._collection = self._client.create_collection(
                    COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"Created new Chroma collection '{COLLECTION_NAME}'")
        except Exception as e:
            logger.error(f"Chroma init failed: {e}")
            self._client = None

    # ── Document Management ──

    def add_document(self, text: str, metadata: Optional[Dict] = None, similarity_threshold: float = 0.95) -> bool:
        """Add a document to the knowledge base.
        
        Args:
            text: Document text content.
            metadata: Optional metadata dict (must include 'task_id' for task-level dedup).
            similarity_threshold: Cosine similarity threshold for dedup (1.0 = exact only).
                Set to 0 to skip similarity check.
        """
        if not self._collection or not text.strip():
            return False

        try:
            doc_id = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
            # 1) Exact text dedup
            try:
                existing = self._collection.get(ids=[doc_id])
                if existing and existing.get("ids"):
                    return False
            except Exception:
                pass

            # 2) Similarity-based dedup (optional, skip if threshold == 0)
            if similarity_threshold > 0 and self._collection.count() > 0:
                try:
                    sim_results = self._collection.query(
                        query_texts=[text],
                        n_results=1,
                    )
                    if sim_results.get("distances") and sim_results["distances"][0]:
                        min_dist = sim_results["distances"][0][0]
                        similarity = 1 - min_dist
                        if similarity >= similarity_threshold:
                            logger.debug(f"Similarity dedup: {similarity:.3f} >= {similarity_threshold}, skipping")
                            return False
                except Exception:
                    pass

            chunks = self._chunk_text(text)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_{i}"
                chunk_meta = {
                    ** (metadata or {}),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "added_at": datetime.utcnow().isoformat(),
                }
                self._collection.add(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[chunk_meta],
                )
            return True
        except Exception as e:
            logger.warning(f"Add document failed: {e}")
            return False

    def add_task_result(self, task_data: Dict) -> bool:
        """Extract and add knowledge from a completed task.
        
        Automatically skips if task_id already exists in the knowledge base (task-level dedup).
        """
        added = False
        task_id = task_data.get("id", "")
        if not task_id:
            return False

        # Task-level dedup: check if any chunk with this task_id exists
        if self._collection:
            try:
                existing = self._collection.get(where={"task_id": task_id})
                if existing and existing.get("ids"):
                    logger.info(f"Task {task_id} already in knowledge base, skipping")
                    return False
            except Exception:
                pass

        user_input = task_data.get("user_input", "")
        subtasks = task_data.get("subtasks", [])

        # Add user requirement as knowledge
        if user_input:
            added |= self.add_document(
                f"Task requirement: {user_input}",
                {"source": "task", "task_id": task_id, "type": "requirement"},
            )

        # Add subtask outputs
        for st in subtasks:
            desc = st.get("description", "")
            summary = st.get("output_summary", "")
            if isinstance(summary, str):
                try:
                    summary = json.loads(summary)
                except Exception:
                    pass

            if isinstance(summary, dict):
                text_parts = [desc]
                if summary.get("summary"):
                    text_parts.append(summary["summary"])
                if summary.get("files"):
                    text_parts.append(f"Files: {', '.join(summary['files'])}")
                if summary.get("score") is not None:
                    text_parts.append(f"PM Score: {summary['score']}/100")

                content = "\n".join(text_parts)
                if len(content) > 20:
                    added |= self.add_document(
                        content,
                        {
                            "source": "subtask",
                            "task_id": task_id,
                            "role": st.get("role", ""),
                            "type": "execution_result",
                        },
                    )

        if added:
            logger.info(f"Task {task_id} knowledge added to RAG ({self._collection.count()} docs)")

        return added

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID prefix"""
        if not self._collection:
            return False
        try:
            results = self._collection.get(where={"doc_id": doc_id})
            if results and results.get("ids"):
                self._collection.delete(ids=results["ids"])
                return True
        except Exception as e:
            logger.warning(f"Delete failed: {e}")
        return False

    def get_knowledge_stats(self) -> Dict:
        """Get knowledge base statistics"""
        if not self._collection:
            return {"count": 0, "sources": {}}
        try:
            count = self._collection.count()
            results = self._collection.get(limit=count)
            sources = {}
            for meta in (results.get("metadatas") or []):
                src = meta.get("source", "unknown") if meta else "unknown"
                sources[src] = sources.get(src, 0) + 1
            return {"count": count, "sources": sources}
        except Exception as e:
            return {"count": 0, "sources": {}, "error": str(e)}

    # ── Query ──

    def query(self, question: str, k: int = TOP_K_DEFAULT) -> List[Dict]:
        """Retrieve relevant documents for a question"""
        if not self._collection:
            return []

        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=min(k, self._collection.count() or k),
            )
            docs = []
            for i in range(len(results.get("ids", [[]])[0])):
                docs.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
            return docs
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return []

    async def answer_question(self, question: str, k: int = TOP_K_DEFAULT) -> Dict:
        """Full RAG pipeline: retrieve + generate answer with citations"""
        # Check cache
        q_hash = hashlib.md5(question.lower().strip().encode("utf-8")).hexdigest()
        cached = self._cache.get(q_hash)
        if cached:
            # Check recency
            logger.info(f"RAG cache hit for: {question[:50]}")
            return cached

        # Retrieve
        docs = self.query(question, k=k)
        if not docs:
            # No knowledge found, fall back to LLM without context
            answer = await self._generate_answer(question, [], no_context=True)
            result = {"answer": answer, "sources": [], "from_cache": False}
            self._cache[q_hash] = result
            # Trim cache
            if len(self._cache) > CACHE_SIZE:
                self._cache.pop(next(iter(self._cache)))
            return result

        # Generate answer with context
        context_parts = []
        sources = []
        seen_sources = set()
        for doc in docs:
            text = doc.get("text", "")
            meta = doc.get("metadata", {})
            source_key = f"{meta.get('source', 'kb')}:{meta.get('task_id', '')}"
            if source_key not in seen_sources and text:
                context_parts.append(text)
                seen_sources.add(source_key)
                sources.append({
                    "text": text[:200],
                    "source": meta.get("source", "knowledge_base"),
                    "task_id": meta.get("task_id", ""),
                    "relevance": round(1 - doc.get("distance", 0), 3),
                })

        context = "\n\n---\n\n".join(context_parts)
        answer = await self._generate_answer(question, context_parts)

        result = {
            "answer": answer,
            "sources": sources[:k],
            "from_cache": False,
        }
        # Cache
        self._cache[q_hash] = result
        if len(self._cache) > CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))

        return result

    def clear_cache(self):
        self._cache.clear()
        logger.info("RAG cache cleared")

    # ── Private Helpers ──

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks by paragraphs with max size"""
        if len(text) <= CHUNK_SIZE:
            return [text]

        paragraphs = text.split("\n")
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 1 > CHUNK_SIZE and current:
                chunks.append(current)
                # Overlap: keep last CHUNK_OVERLAP chars
                current = current[-CHUNK_OVERLAP:] if len(current) > CHUNK_OVERLAP else ""
            current = (current + "\n" + para).strip() if current else para
        if current:
            chunks.append(current)
        return chunks or [text]

    async def _generate_answer(self, question: str, context_chunks: List[str], no_context: bool = False) -> str:
        """Generate answer using LLM with context"""
        llm_cfg = self.llm_config or {}
        try:
            if no_context or not context_chunks:
                prompt = f"""用户问了一个问题，但知识库中没有找到相关信息。请如实告知用户，并根据你自己的知识给出一般性回答。

问题：{question}

注意：如果这个问题是关于本系统功能或代码的，建议用户提供更多上下文或检查文档。"""
                system_prompt = "你是一个知识库问答助手。如果知识库中没有相关信息，请如实告知，不要编造。"
            else:
                context = "\n\n---\n\n".join(context_chunks)
                prompt = f"""请基于以下知识库内容回答用户的问题。如果知识库内容不足，请如实说明。

## 知识库内容
{context}

## 用户问题
{question}

请给出简洁准确的回答，并在最后列出引用来源（知识片段的前20个字符）。"""
                system_prompt = "你是一个知识库问答助手。请基于提供的知识内容回答问题，并在回答末尾标注引用来源。回答要简洁准确。"

            # Use LLMFactory with the provided config, fallback to embedding config
            return await LLMFactory.chat(
                "rag",
                llm_cfg or {"api_key": EMBEDDING_API_KEY, "api_base_url": EMBEDDING_BASE_URL, "model_name": "Qwen/Qwen2.5-72B-Instruct-128K"},
                prompt,
                system_prompt,
            )
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"回答生成失败: {str(e)}"
