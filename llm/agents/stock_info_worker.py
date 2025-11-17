# llm/agents/time_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

prompt = """
너는 종목 정보를 조회하는 전문 에이전트다.

- 사용자가 한국 종목 이름을 입력하면
  반드시 get_stock_symbol(stock_name)를 호출해라.

- tool 결과를 받은 후에는 결과를 기반으로
  종목 코드, 종목명, 시장, 기타 필드를 요약하여
  하나의 assistant 메시지로 출력하라.

- 절대 '조회가 완료되었습니다' 같은 메타 발언을 하지 말고
  tool 결과만을 기반으로 명확한 사용자 응답을 만들어라.

- MCP tool을 호출할 때마다 반드시 사람의 승인을 받아야 한다.
"""

def make_stock_info_worker(llm, tools):
    print("[DEBUG] make_stock_info_worker called")

    # ⚠️ tools를 강제로 get_current_time 하나만 받도록 설정
    filtered_tools = [t for t in tools if t.name == "get_stock_symbol"]

    print(f"[DEBUG] Filtered tools (only get_stock_symbol): {filtered_tools}")
    agent = create_agent(
        model=llm,
        tools=filtered_tools,  # [get_stock_symbol]
        system_prompt=prompt,
        name="stock_info_worker",

        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "get_stock_symbol": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ]
    )
    return agent