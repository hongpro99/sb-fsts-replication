# llm/agents/time_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

class TimeAgentState(TypedDict):
    messages: List
    human_feedback: Optional[dict]

prompt = """
너는 사용자에게 현재 시간과 날짜를 알려주는 전문 에이전트야.
어떤 MCP 툴을 실행할 때마다 반드시 사람의 승인을 받아야 한다.
"""

def make_time_worker(llm, tools):
    """
    LangChain create_agent 기반 최신 Worker 생성기.
    LangGraph가 Worker를 실행 엔진으로 다룬다.
    """
    agent = create_agent(
        model=llm,
        tools=tools,                     # MCP tools
        system_prompt=prompt,
        name="time_worker",
        state_schema=TimeAgentState,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    # MCP tool 이름을 정확히 명시해야 한다.
                    # 필요시 여러 MCP tool 추가 가능
                    "get_current_time": {
                        "allowed_decisions": ["approve", "reject", "edit"] #approve = 실행, reject  = 실행 취소, edit = 재계획(plan again)
                    }
                }
            )
        ]
    )
    return agent