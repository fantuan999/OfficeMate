from typing import Optional

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import DASHSCOPE_API_KEY, LLM_MODEL, MAX_HISTORY_ROUNDS
from services.retriever_service import retrieve

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
回答请使用 Markdown 格式，结构清晰。"""

USER_PROMPT_TEMPLATE = """问题类型：{question_type}
分类范围：{category}

参考材料：
{context}

用户问题：{question}

请根据参考材料回答，如有操作步骤请分点列出，如有风险或注意事项请单独说明。"""


def _infer_question_type(question: str) -> str:
    """根据关键词推断问题类型，影响 prompt 中的引导方向"""
    for q_type, keywords in _QUESTION_TYPE_KEYWORDS.items():
        if any(kw in question for kw in keywords):
            return q_type
    return "咨询"


def _build_context(chunks: list[dict]) -> str:
    """将检索到的 chunk 列表拼成 prompt 中的参考材料文本"""
    if not chunks:
        return "（知识库中暂无相关文档）"
    return "\n\n---\n\n".join(
        f"【来源：{c['source']}】\n{c['content']}" for c in chunks
    )


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
    RAG 问答主流程：检索 → 构建 prompt → 调用 LLM → 返回结构化结果

    参数：
        question: 用户问题
        category: 文档分类过滤
        history:  历史对话，格式 [{"question": str, "answer": str}, ...]

    返回：
        {
            "answer": str,        # LLM 回答
            "sources": list[str], # 引用文档名（去重）
            "chunks": list[dict], # 检索到的原始 chunk
            "question_type": str, # 推断的问题类型
        }
    """
    # 1. 推断问题类型
    question_type = _infer_question_type(question)

    # 2. 检索相关 chunk
    chunks = retrieve(question, category)

    # 3. 构建 prompt（system + 历史消息占位符 + 用户消息）
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", USER_PROMPT_TEMPLATE),
    ])

    # 4. 初始化 LLM
    llm = ChatTongyi(
        model=LLM_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )

    # 5. 组装链：prompt → llm → 字符串输出
    chain = prompt | llm | StrOutputParser()

    # 6. 执行
    answer = chain.invoke({
        "history": _build_history_messages(history or []),
        "question_type": question_type,
        "category": category or "全部",
        "context": _build_context(chunks),
        "question": question,
    })

    return {
        "answer": answer,
        "sources": list({c["source"] for c in chunks}),
        "chunks": chunks,
        "question_type": question_type,
    }
