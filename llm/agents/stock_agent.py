from typing import Dict, Any
from fastmcp import Client
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
import asyncio

def stock_agent(state: Dict[str, Any]) -> Command:
    """심볼 정보 등 MCP 호출 + 필요 시 HITL로 handoff."""
    query = state["task"]
    #llm 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
        )
    reasoning = llm.invoke([{"role": "user", "content": f"'{query}' 관련 기술적 분석 개요를 한국어로 간단히."}]).content

    async def run_client():
        async with Client("http://127.0.0.1:8005/sse") as client:
            return await client.call_tool("get_stock_symbol", {"symbol": query})
    tool_result = asyncio.run(run_client())
    

    # 응답 업데이트
    update = {
        "response": f"[Stock Agent]\n{reasoning}\n\n[MCP]\n{tool_result}",
        "handled_by": "stock_agent",
    }
    # require_human 플래그에 따라 다음 노드 결정
    if state.get("require_human"):
        return Command(update=update, goto="human_review_agent")
    else:
        return Command(update=update, goto=END)
