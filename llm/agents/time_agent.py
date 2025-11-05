#LLM 호출 테스트 코드

from typing import Dict, Any
from fastmcp import Client
from langgraph.types import Command
from langgraph.graph import END
from langchain_openai import AzureChatOpenAI
import asyncio

def time_agent(state: Dict[str, Any]) -> Command:
    """현재시간 MCP 호출 + 필요 시 HITL로 handoff."""
    query = state["task"]
    #llm 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
        )

    async def run_client():
        async with Client("http://127.0.0.1:8005/sse") as client:
            return await client.call_tool("get_current_time")

    current_time = asyncio.run(run_client())

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "너는 현재 시간을 사용자에게 친절하고 자연스럽게 알려주는 에이전트야. "
                "날짜, 시간, 요일 등을 읽기 좋게 표현하고, 불필요한 코드나 숫자는 제외해. "
                "한국어로 대답해야 해."
            )
        },
        {
            "role": "user",
            "content": (
                f"현재 MCP 서버에서 받은 시간은 다음과 같아:\n{current_time}\n"
                "이 값을 사람이 이해하기 쉬운 문장으로 자연스럽게 표현해줘."
            )
        }
    ]
    
    llm_response = llm.invoke(prompt_messages)
    natural_text = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        
    update = {
        "response": f"[time_agent]\n{natural_text}",
        "handled_by": "time_agent",
    }
    if state.get("require_human"):
        return Command(update=update, goto="human_review_agent")
    else:
        return Command(update=update, goto=END)