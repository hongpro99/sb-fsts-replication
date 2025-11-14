# 시뮬레이션 혹은 거래 결과를 confluence에 정리

from typing import Dict, Any
from fastmcp import Client
from langchain_openai import AzureChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
import asyncio

def portfolio_agent(state: Dict[str, Any]) -> Command:
    # sourcery skip: assign-if-exp
    """특정 봇 + 종목 잔고를 MCP 툴로 조회하고, 포트폴리오 해석 제공"""
    query = state["task"]

    # 🔹 LLM 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
    )

    # 🔹 1️⃣ LLM 해석
    reasoning = llm.invoke([
        {"role": "user", "content": f"'{query}' 관련 포트폴리오 또는 잔고 정보를 요약하고 간단히 해석해줘."}
    ]).content

    # 🔹 2️⃣ MCP 호출
    async def run_client():
        async with Client("http://127.0.0.1:8005/sse") as client:
            # 예: "bnuazz15bot 005930" 형태의 질의에서 봇 이름과 심볼 추출
            import re
            match = re.search(r"(\w+)\s+(\w+)", query)
            if match:
                bot_name, symbol = match.groups()
            else:
                bot_name, symbol = "unknown_bot", query
            return await client.call_tool("get_auto_trading_balance", {
                "trading_bot_name": bot_name,
                "symbol": symbol
            })

    tool_result = asyncio.run(run_client())

    # 🔹 3️⃣ 응답 구성
    update = {
        "response": f"[Portfolio Agent]\n{reasoning}\n\n[MCP 결과]\n{tool_result}",
        "handled_by": "portfolio_agent",
    }

    # 🔹 4️⃣ Human-in-the-loop 여부에 따라 다음 단계 결정
    if state.get("require_human"):
        return Command(update=update, goto="human_review_agent")
    else:
        return Command(update=update, goto=END)
