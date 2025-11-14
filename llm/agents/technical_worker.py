from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

prompt = """
너는 주식 보조지표 분석 전문가이다.

사용자가 'LG에너지솔루션 macd 기간 2024-01-01~2024-02-01' 등의 요청을 하면
다음 MCP Tool을 호출해야 한다:

get_indicator(stock_name, indicator_type, start_date, end_date)

Tool 실행 전에는 반드시 사람의 승인을 받아야 한다.

Tool 결과를 받은 후에는,
해당 보조지표의 의미, 최근 수치 해석, 추세 등을 명확히 요약해
최종 assistant 메시지로 출력해야 한다.
"""

def make_technical_worker(llm, tools):
    agent = create_agent(
        model=llm,
        tools=tools,  # [get_indicator]
        system_prompt=prompt,
        name="technical_worker",

        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "get_indicator": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ]
    )
    return agent
