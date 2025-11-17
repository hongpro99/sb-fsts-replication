# llm/agents/time_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import ( #hooking
    HumanInTheLoopMiddleware, 
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional
from pydantic import BaseModel

class TimeResponse(BaseModel):
    datetime: str
    date: str
    time: str
    timezone: str

prompt = """
너는 사용자에게 현재 시간과 날짜를 알려주는 전문 에이전트야.
어떤 MCP 툴을 실행할 때마다 반드시 사람의 승인을 받아야 한다.

반드시 MCP tool `get_current_time`을 호출해야 하며,
tool 결과를 기반으로 아래 TimeResponse 구조로 응답을 만들어야 한다.

TimeResponse 구조:
- datetime: 전체 날짜시간 (예: 2025-01-03 13:05:22)
- date: YYYY-MM-DD
- time: HH:MM:SS
- timezone: Asia/Seoul
"""

def make_time_worker(llm, tools):
    """
    LangChain create_agent 기반 최신 Worker 생성기.
    LangGraph가 Worker를 실행 엔진으로 다룬다.
    """
    
    print("[DEBUG] make_time_worker called")

    # ⚠️ tools를 강제로 get_current_time 하나만 받도록 설정
    filtered_tools = [t for t in tools if t.name == "get_current_time"]

    print(f"[DEBUG] Filtered tools (only get_current_time): {filtered_tools}")
    agent = create_agent(
        model=llm,
        tools=filtered_tools,                     # MCP tools
        system_prompt=prompt,
        name="time_worker",
        response_format=ProviderStrategy(TimeResponse),
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