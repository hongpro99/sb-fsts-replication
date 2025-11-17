# llm/agents/rag_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

prompt= """
너는 문서 기반 RAG 검색(QA) 전문 에이전트다.

사용자가 질문을 하면 반드시 다음 MCP Tool을 사용해 문서를 검색해야 한다:

    rag_search(query)

Tool을 호출하기 전에 반드시 사람의 승인을 받아야 한다.

Tool 실행 후에는 RAG 파이프라인이 반환한 '문맥(context)'을 기반으로
최종 사용자 응답을 생성해야 한다.

### 중요한 지침
- 최종 assistant 메시지는 다음 구조를 따라야 한다:

질문:
{query}

문맥:
{context}

답변:
{final_answer}

- 여기서 {context}는 RAG tool이 반환한 문서 기반 정보이고,
  {final_answer}는 문맥을 근거로 한 네가 생성하는 최종 답변이다.
"""
def make_rag_worker(llm, tools):
    print("[DEBUG] make_rag_worker called")

    # ⚠️ tools를 강제로 get_current_time 하나만 받도록 설정
    filtered_tools = [t for t in tools if t.name == "rag_search"]

    print(f"[DEBUG] Filtered tools (only rag_search): {filtered_tools}")
    agent = create_agent(
        model=llm,
        tools=filtered_tools,                         # [rag_search]
        system_prompt=prompt,
        name="rag_worker",
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "rag_search": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ]
    )
    return agent