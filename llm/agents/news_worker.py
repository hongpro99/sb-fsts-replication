# llm/agents/news_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

prompt = """
너는 금융 뉴스 분석 전문가야.
사용자로부터 종목명을 입력받으면 관련 뉴스를 가져오고
요약과 감성 분석(긍정/부정/중립)을 제공하고 supervisor에 그대로 응답해줘.

단, MCP Tool을 실행할 때는 반드시 사람의 승인을 받아야 한다.
"""

def make_news_worker(llm, tools):
    """
    LangChain create_agent 기반 뉴스 Worker.
    MCP tool 호출 전에 반드시 HITL 승인을 거친다.
    """
    print("[DEBUG] make_news_worker called")

    # ⚠️ tools를 강제로 get_current_time 하나만 받도록 설정
    filtered_tools = [t for t in tools if t.name == "get_stock_news_sentiment"]

    print(f"[DEBUG] Filtered tools (only get_stock_news_sentiment): {filtered_tools}")
    
    agent = create_agent(
        model=llm,
        tools=filtered_tools,                     # MCP tools (get_stock_news_sentiment)
        system_prompt=prompt,
        name="news_worker",
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "get_stock_news_sentiment": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ]
    )
    return agent

