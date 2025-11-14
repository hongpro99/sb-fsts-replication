# llm/supervisor/supervisor_workers.py
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.base import BaseCheckpointSaver #RedisSaver, MemorySaver, SQLiteSaver 모두 사용 가능
from langchain_openai import AzureChatOpenAI

# Worker Agents
from llm.agents.time_worker import make_time_worker
from llm.agents.stock_info_worker import make_stock_info_worker
from llm.agents.news_worker import make_news_worker
from llm.agents.common_worker import make_common_worker
from llm.agents.rag_worker import make_rag_worker
from llm.agents.user_info_worker import make_user_info_worker
from llm.agents.technical_worker import make_technical_worker

import os
from dotenv import load_dotenv

load_dotenv()

def build_supervisor(llm: AzureChatOpenAI, tools: list, checkpointer: BaseCheckpointSaver):
    # sourcery skip: inline-immediately-returned-variable
    """
    Supervisor/Workers 구조를 구성하는 그래프를 빌드합니다.
    - Supervisor는 사용자의 요청을 분석해 각 Worker에게 작업을 분배
    - Worker는 MCP ToolNode를 사용해 실제 실행 담당
    """

    
    # ✅ 생성 시점에 tool_hub를 주입해서 에이전트 생성
    time_worker  = make_time_worker(llm, tools)
    stock_info_worker = make_stock_info_worker(llm, tools)
    news_worker  = make_news_worker(llm, tools)
    rag_worker = make_rag_worker(llm,tools)
    common_worker = make_common_worker(llm)
    user_info_worker = make_user_info_worker(llm,tools)
    technical_worker = make_technical_worker(llm,tools)
    
    supervisor_prompt = """
    너는 중앙 Supervisor야.
    사용자의 질문을 분석해서 어떤 Worker를 호출할지 판단해.
    - 시간/날짜 관련 → time_worker
    - 특정 종목 정보 조회 → stock_info_worker
    - 뉴스 요약, 감성 분석 → news_worker
    - 문서 기반 정보, 회사 리포트, 보고서, PDF, 메뉴얼, 가이드라인 관련 -> rag_worker
    - 사용자 id 기반 정보 조회, 잔고 조회 -> user_info_worker
    - 특정 종목의 기술적 지표, 보조지표 조회 -> technical_worker
    - 그 외의 일반적인 질문 -> common_worker
    직접 일을 하지 말고, 적절한 Worker에게만 일을 맡겨.
    
    다음 내용은 꼭 지켜야 해.
    -절대 새로운 응답을 생성하지 말 것.
    -worker가 생성한 assistant 메시지를 그대로 출력할 것.
    -worker 메시지를 요약, 재해석, 재작성하지 말 것.
    """

    # Supervisor 생성
    supervisor = create_supervisor(
        model=llm,
        agents=[time_worker, stock_info_worker, news_worker, common_worker, rag_worker, user_info_worker, technical_worker],
        prompt=supervisor_prompt,
        state_schema=None,
        parallel_tool_calls=True,
        output_mode="full_history" # or summary
    )

    # Checkpointer로 그래프 컴파일
    supervisor_graph = supervisor.compile(checkpointer=checkpointer)
    return supervisor_graph


