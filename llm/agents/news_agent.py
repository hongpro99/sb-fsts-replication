from typing import Dict, Any
from fastmcp import Client
from langgraph.types import Command
from langgraph.graph import END
import asyncio

def news_agent(state: Dict[str, Any]) -> Command:
    """뉴스/감성 MCP 호출 + 필요 시 HITL로 handoff."""
    query = state["task"]
    
    async def run_client():
        async with Client("http://127.0.0.1:8005/sse") as client:
            return await client.call_tool("get_stock_news_sentiment", {"stock_name": query, "only_today": True})

    news = asyncio.run(run_client())
    
    update = {
        "response": f"[News Agent]\n{news}",
        "handled_by": "news_agent",
    }
    if state.get("require_human"):
        return Command(update=update, goto="human_review_agent")
    else:
        return Command(update=update, goto=END)
