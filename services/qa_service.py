from typing import Optional

from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from config import DASHSCOPE_API_KEY, LLM_MODEL, MAX_HISTORY_ROUNDS
from services.retriever_service import format_docs, get_retriever

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

回答必须严格按照以下三段 Markdown 结构输出，不得省略任何段落标题：

### 最终回答
（直接回答用户问题，1-3 句话）

### 操作步骤/材料清单
（如有步骤或所需材料，分点列出；如无则填"无"）

### 风险提示
（注意事项、例外情况或可能的风险；如无则填"无"）"""

USER_PROMPT_TEMPLATE = """问题类型：{question_type}
分类范围：{category}

参考材料：
{context}

用户问题：{question}

请严格按照三段结构（### 最终回答 / ### 操作步骤/材料清单 / ### 风险提示）输出。"""


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
    RAG 问答主流程（LCEL 风格）

    参数：
        question: 用户问题
        category: 文档分类过滤
        history:  历史对话，格式 [{"question": str, "answer": str}, ...]

    返回：
        {
            "answer": str,        # LLM 回答
            "sources": list[str], # 引用文档名（去重）
            "question_type": str, # 推断的问题类型
        }
    """
    question_type = _infer_question_type(question)
    retriever = get_retriever(category)

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", USER_PROMPT_TEMPLATE),
    ])

    llm = ChatTongyi(model=LLM_MODEL, dashscope_api_key=DASHSCOPE_API_KEY)

    # ── LCEL chain（黑马风格）────────────────────────────────
    # retriever 直接串进 chain，|format_docs 把 Document 列表转成字符串
    # RunnablePassthrough() 把原始输入（question）原样传到下一步
    # RunnableLambda(lambda _: ...) 忽略输入，注入静态值（问题类型/分类/历史）
    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "question_type": RunnableLambda(lambda _: question_type),
            "category": RunnableLambda(lambda _: category or "全部"),
            "history": RunnableLambda(lambda _: _build_history_messages(history or [])),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    answer = rag_chain.invoke(question)

    # 单独调用 retriever 拿来源文件名（用于 UI 显示引用）
    docs = retriever.invoke(question)
    sources = list({d.metadata.get("source_filename", "未知") for d in docs})

    return {
        "answer": answer,
        "sources": sources,
        "question_type": question_type,
    }
