from typing import Optional

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import DASHSCOPE_API_KEY, LLM_MODEL, MAX_HISTORY_ROUNDS
from services.retriever_service import format_docs, get_retriever
from services.cache_service import get_cached_answer, set_cache

# ── 问题类型关键词映射 ──────────────────────────────────────
_QUESTION_TYPE_KEYWORDS = {
    "清单": ["有哪些", "列举", "清单", "列表", "都有什么"],
    "流程": ["怎么", "如何", "步骤", "流程", "申请", "办理", "操作"],
    "公告": ["通知", "公告", "最新", "近期", "政策变化"],
    "咨询": [],  # 默认类型
}

SYSTEM_PROMPT = """你是 OfficeMate，一个企业内部政策和流程智能助手。
你只能依据给定的参考材料回答问题，不能编造制度、审批规则或联系方式。
如果参考材料中没有相关信息，请如实说明。
回答使用 Markdown 格式，结构清晰。
- 如果回答涉及操作步骤或所需材料，请加上 ### 操作步骤/材料清单 段落分点列出。
- 如果有注意事项、例外情况或风险，请加上 ### 风险提示 段落说明。
- 简单问题直接回答即可，无需强制添加以上段落。"""

USER_PROMPT_TEMPLATE = """问题类型：{question_type}
分类范围：{category}

参考材料：
{context}

用户问题：{question}"""


def _infer_question_type(question: str) -> str:
    """根据关键词推断问题类型，影响 prompt 中的引导方向"""
    for q_type, keywords in _QUESTION_TYPE_KEYWORDS.items():
        if any(kw in question for kw in keywords):
            return q_type
    return "咨询"


def _build_history_messages(history: list[dict]) -> list:
    """将历史对话转成 LangChain 消息对象，最多保留 MAX_HISTORY_ROUNDS 轮"""
    messages = []
    for turn in history[-MAX_HISTORY_ROUNDS:]:
        messages.append(HumanMessage(content=turn["question"]))
        messages.append(AIMessage(content=turn["answer"]))
    return messages


def ask(
    question: str,
    category: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> dict:
    """
    RAG 问答主流程。

    参数：
        question: 用户问题
        category: 文档分类过滤
        history:  历史对话，格式 [{"question": str, "answer": str}, ...]

    返回：
        {
            "answer": str,
            "sources": list[str],
            "question_type": str,
            "cache_hit": bool,
        }
    """
    question_type = _infer_question_type(question)

    # ── 1. 查语义缓存 ──────────────────────────────────────
    cached = get_cached_answer(question)
    if cached:
        return {
            "answer": cached,
            "sources": [],
            "question_type": question_type,
            "cache_hit": True,
        }

    # ── 2. Cache MISS：走完整 RAG pipeline ─────────────────
    # 先调 retriever 拿 docs，同时得到 context 和 sources（只调一次）
    retriever = get_retriever(category)
    docs = retriever.invoke(question)
    context = format_docs(docs)
    sources = list({d.metadata.get("source_filename", "未知") for d in docs})

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", USER_PROMPT_TEMPLATE),
    ])

    llm = ChatTongyi(model=LLM_MODEL, dashscope_api_key=DASHSCOPE_API_KEY)
    rag_chain = prompt | llm | StrOutputParser()

    answer = rag_chain.invoke({
        "context": context,
        "question": question,
        "question_type": question_type,
        "category": category or "全部",
        "history": _build_history_messages(history or []),
    })

    # ── 3. 存入缓存 ────────────────────────────────────────
    set_cache(question, answer)

    return {
        "answer": answer,
        "sources": sources,
        "question_type": question_type,
        "cache_hit": False,
    }
