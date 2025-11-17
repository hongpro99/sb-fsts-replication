# llm/supervisor/supervisor_workers.py
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.base import BaseCheckpointSaver #RedisSaver, MemorySaver, SQLiteSaver 모두 사용 가능
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

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

    중요 규칙:

    1. 사용자의 요청은 여러 개의 작업을 포함할 수 있다.
    예: "현재 시각 알려주고 id1 계정 정보도 알려줘"
    → 이것은 두 개의 독립된 작업이다.

    2. 너의 역할은 사용자의 요청을 분석하여
    필요한 작업 단위를 모두 식별하고,
    각 작업을 가장 잘 처리할 worker에게 순서대로 위임하는 것이다.

    3. 여러 worker를 순차적으로 실행해야 하는 경우:
    - 첫 번째 worker를 실행하고 그 결과를 기다린다.
    - 그 결과를 state 에 추가한다.
    - 다음 필요한 worker를 실행한다.
    이 과정을 모든 작업이 완료될 때까지 반복한다.
    
    5. 만약 요청이 여러 worker의 능력을 동시에 요구하면
    반드시 복수 worker를 순차적으로 실행해야 한다.

    6. worker가 structured_response(JSON)를 반환하면
    이 값은 이미 최종 결과이며,
    supervisor는 이를 수정하거나 자연어로 재작성하지 않는다.
    그대로 state에 저장하여 다음 worker나 최종 응답으로 사용한다.

    7. 모든 작업이 완료되면,
    worker들의 결과를 state로부터 종합하여 최종 응답을 생성한다.
    
    8. 한 번의 응답에서 두 개 이상의 worker로 동시에 transfer_to_* tool을 호출하지 말고,
    항상 하나의 worker만 선택해서 차례로 실행해야 한다.
    """


    # Supervisor 생성
    supervisor = create_supervisor(
        model=llm,
        agents=[time_worker, stock_info_worker, news_worker, common_worker, rag_worker, user_info_worker, technical_worker],
        prompt=supervisor_prompt,
        state_schema=None,
        parallel_tool_calls=False,
        #add_handoff_back_messages=True,
        output_mode="full_history" # or summary
    )
    
    # Checkpointer로 그래프 컴파일
    supervisor_graph = supervisor.compile(checkpointer=checkpointer)
    return supervisor_graph

# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# from langgraph.graph import StateGraph, END
# from typing import TypedDict, List, Optional
# from pydantic import BaseModel

# # 너의 worker 생성 함수들
# from llm.agents.time_worker import make_time_worker
# from llm.agents.news_worker import make_news_worker
# from llm.agents.common_worker import make_common_worker
# from llm.agents.user_info_worker import make_user_info_worker
# from llm.agents.stock_info_worker import make_stock_info_worker
# from llm.agents.rag_worker import make_rag_worker
# from llm.agents.technical_worker import make_technical_worker


# # ------------------------------
# # 그래프 State 정의
# # ------------------------------
# class AgentState(TypedDict):
#     messages: List[dict]       # 메시지 히스토리
#     next_worker: Optional[str] # supervisor가 결정한 다음 worker 이름
#     finished: bool             # 끝났는지 여부


# # ------------------------------
# # Supervisor Node (LLM 기반 라우터)
# # ------------------------------
# def make_supervisor_node(llm):

#     system_prompt = """
# 너는 중앙 Supervisor다.
# 너의 역할은 '사용자의 요청과 현재 state만 보고' 다음에 실행할 worker를 결정하는 것이다.

# 절대로 최종 응답을 생성하지 마라.
# 절대로 worker의 메시지를 요약하거나 변형하지 마라.
# 오직 다음 worker 이름만 결정하라.

# 다음 worker가 모두 끝났으면 FINISH를 반환하라.
# """

#     def supervisor_node(state: AgentState):
#         msgs = state["messages"]

#         # LLM 호출
#         ai = llm.invoke([
#             SystemMessage(content=system_prompt),
#             *[HumanMessage(content=m["content"]) if m["role"]=="user" 
#               else AIMessage(content=m["content"], name=m.get("name")) for m in msgs]
#         ])

#         text = ai.content.strip()

#         # LLM이 "FINISH" 라고 말하면 종료
#         if "FINISH" in text:
#             return {"finished": True}

#         # 아니면 worker 이름 하나 반환해야 함
#         worker_name = text
#         return {"next_worker": worker_name, "finished": False}

#     return supervisor_node


# # ------------------------------
# # Output Node (Pass-through)
# # ------------------------------
# def output_node(state: AgentState):
#     """
#     마지막 worker 메시지를 그대로 반환한다.
#     """
#     msgs = state["messages"]
#     # worker의 마지막 assistant 메시지 찾기
#     for m in reversed(msgs):
#         if m["role"] == "assistant" and m.get("name") != "supervisor":
#             return {"final_response": m["content"]}

#     # fallback
#     return {"final_response": ""}


# # ------------------------------
# # Supervisor Graph Builder
# # ------------------------------
# def build_supervisor(llm, tools, checkpointer):

#     # Worker 생성
#     time_worker = make_time_worker(llm, tools)
#     stock_worker = make_stock_info_worker(llm, tools)
#     news_worker = make_news_worker(llm, tools)
#     rag_worker = make_rag_worker(llm, tools)
#     common_worker = make_common_worker(llm)
#     user_worker = make_user_info_worker(llm, tools)
#     tech_worker = make_technical_worker(llm, tools)

#     workers = {
#         "time_worker": time_worker,
#         "stock_info_worker": stock_worker,
#         "news_worker": news_worker,
#         "rag_worker": rag_worker,
#         "common_worker": common_worker,
#         "user_info_worker": user_worker,
#         "technical_worker": tech_worker,
#     }

#     # Supervisor LLM Router
#     supervisor_node = make_supervisor_node(llm)

#     # 그래프 생성
#     graph = StateGraph(AgentState)
#     graph.add_node("supervisor", supervisor_node)

#     # worker 노드들 추가
#     for name, worker in workers.items():
#         graph.add_node(name, worker)

#     # output node
#     graph.add_node("output_node", output_node)

#     # supervisor → worker → supervisor … 반복
#     # worker 실행 뒤 supervisor로 돌아감
#     for name in workers.keys():
#         graph.add_edge(name, "supervisor")

#     # supervisor가 next_worker를 정해서 이동
#     def supervisor_router(state: AgentState):
#         if state.get("finished"):
#             return "output_node"
#         return state.get("next_worker")

#     graph.add_conditional_edges("supervisor", supervisor_router)

#     # output_node → END
#     graph.add_edge("output_node", END)

#     graph.set_entry_point("supervisor")

#     return graph.compile(checkpointer=checkpointer)


