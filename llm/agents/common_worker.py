# llm/agents/time_worker.py
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent

prompt="""너는 일반적인 질의응답, 대화, 지식 기반 응답을 담당하는 공용 에이전트야.
    MCP 툴을 따로 호출하지 않고 일반적인 질문에 응답하면 돼.
    """
        
def make_common_worker(llm):
    
    return create_agent(
        model=llm,
        tools=[],  # ✅ 생성 시점에 주입
        name="common_worker",
        system_prompt=prompt
    )