from typing import Dict, Any
from fastmcp import Client
from langchain_openai import AzureChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
import asyncio

def technical_agent(state: Dict[str, Any]) -> Command:
    """보조지표 MCP 툴을 호출하여 기술분석 결과를 요약"""
    query = state["task"]

    # 🔹 LLM 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
    )

    # 1️⃣ 사용자 요청에서 보조지표 종류 추출
    reasoning = llm.invoke([
        {"role": "user", "content": f"'{query}' 문장에서 필요한 보조지표를 하나 추출하고 "
                                    f"지표 이름만 영어로 답해줘 (예: rsi, macd, bollinger, mfi, stochastic, ema, sma, wma 중 하나)."}
    ]).content.strip().lower()

    # 기본값 설정
    indicator_type = reasoning if reasoning in [
        "rsi", "macd", "bollinger", "mfi", "stochastic", "ema", "sma", "wma"
    ] else "rsi"

    # 2️⃣ MCP 호출
    async def run_client():
        async with Client("http://127.0.0.1:8005/sse") as client:
            # 실제 환경에서는 DB나 API에서 가져온 OHLC 데이터가 여기에 들어감
            sample_data = [
                {"Open": 70000, "High": 71000, "Low": 69000, "Close": 70500, "Volume": 100000},
                {"Open": 70500, "High": 71500, "Low": 70000, "Close": 71200, "Volume": 110000},
                {"Open": 71200, "High": 72000, "Low": 71000, "Close": 71800, "Volume": 105000},
                {"Open": 71800, "High": 72500, "Low": 71500, "Close": 72000, "Volume": 120000},
                {"Open": 72000, "High": 73000, "Low": 71800, "Close": 72800, "Volume": 130000},
                {"Open": 72800, "High": 73500, "Low": 72500, "Close": 73200, "Volume": 125000},
            ]
            return await client.call_tool("get_indicator", {
                "indicator_type": indicator_type,
                "data": sample_data
            })

    tool_result = asyncio.run(run_client())

    # 3️⃣ LLM으로 해석/요약
    summary = llm.invoke([
        {"role": "user", "content": f"보조지표 '{indicator_type}' 결과를 기반으로 현재 시장 흐름을 간단히 한국어로 해석해줘.\n\n{tool_result}"}
    ]).content

    # 4️⃣ 응답 구성
    update = {
        "response": f"[Technical Agent]\n지표 종류: {indicator_type.upper()}\n\n"
                    f"[MCP 결과]\n{tool_result}\n\n"
                    f"[LLM 해석]\n{summary}",
        "handled_by": "technical_agent",
    }

    # 5️⃣ HITL (Human-in-the-loop) 여부에 따라 결정
    if state.get("require_human"):
        return Command(update=update, goto="human_review_agent")
    else:
        return Command(update=update, goto=END)
