# server/api.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel
import redis
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.redis import RedisSaver
from langgraph.types import Command

from llm.agents.supervisor_agent import supervisor_agent
from llm.agents.stock_agent import stock_agent
from llm.agents.news_agent import news_agent
from llm.agents.human_review_agent import human_review_agent
from llm.agents.rag_agent import rag_agent
from llm.agents.portfolio_agent import portfolio_agent
from llm.agents.technical_agent import technical_agent
from llm.agents.time_agent import time_agent

from llm.ingestion.local_index import build_or_update_index

# -----------------------------
# AppState 정의
# -----------------------------
from typing import TypedDict, Literal

class AppState(TypedDict, total=False):
    input: str
    task: str
    response: str #현재 출력 메시지
    handled_by: str #어떤 agent가 응답을 처리했는지
    human_feedback: str
    require_human: bool

# -----------------------------
# FastAPI 초기화
# -----------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    print("🚀 서버 시작 중... 로컬 데이터 인덱싱 준비")
    # 로컬 폴더 인덱싱
    build_or_update_index(data_dirs=["./data/docs"])
    
    builder = StateGraph(AppState)
    builder.add_node("supervisor", supervisor_agent)
    builder.add_node("stock_agent", stock_agent)
    builder.add_node("news_agent", news_agent)
    builder.add_node("human_review_agent", human_review_agent)
    builder.add_node("technical_agent", technical_agent)
    builder.add_node("portfolio_agent", portfolio_agent)
    builder.add_node("rag_agent", rag_agent)
    builder.add_node("time_agent", time_agent)
    
    builder.add_edge(START, "supervisor")
    builder.add_edge("human_review_agent", END)
    #redis_client = redis.Redis(host="127.0.0.1", port=6379, db=0)
    # saver = RedisSaver.from_conn_string("redis://127.0.0.1:6379/0")
    # app.state.graph = builder.compile(checkpointer=saver)
    app.state.graph = builder.compile()

    yield

app = FastAPI(title="Stock AI Graph (lifespan)", lifespan=lifespan)
# -----------------------------
# 요청 모델
# -----------------------------
class ChatRequest(BaseModel):
    session_id: str #LangGraph 세션 ID (thread_id와 동일)
    text: str #
    require_human: bool = False #human 검토가 필요한지

class ResumeRequest(BaseModel):
    session_id: str
    human_feedback: str #사용자가 이전에 입력한 피드백

# -----------------------------
# 1️⃣ /agent_chat — 그래프 시작
# -----------------------------
@app.post("/agent_chat")
def agent_chat(req: ChatRequest):
    print("\n🔄 /agent_chat 호출됨")
    print(f"📨 요청: session_id={req.session_id}, input: {req.text}, require_human: {req.require_human}")
    
    init_state = {"input": req.text, "require_human": req.require_human}
    config = {"configurable": {"thread_id": req.session_id}}
    result = app.state.graph.invoke(init_state, config=config)
    print(f"📦 LangGraph result: {result}")
    
    # interrupt 발생 시 메시지 포함 응답
    if "__interrupt__" in result:
        interrupt_list = result["__interrupt__"]
        interrupt_msg = None
        if isinstance(interrupt_list, list) and len(interrupt_list) > 0:
            # Interrupt 객체의 value 속성 추출
            interrupt_obj = interrupt_list[0]
            interrupt_msg = getattr(interrupt_obj, "value", str(interrupt_obj))
        return {
            "session_id": req.session_id,
            "handled_by": result.get("handled_by", "supervisor_agent"),
            "response": interrupt_msg or "⚠️ 인간 피드백이 필요합니다.", #interrupt가 value를 키워드로 가짐
            "require_human": True,
            "human_feedback": None
        }

    # 일반적인 경우
    return {
        "session_id": req.session_id,
        "handled_by": result.get("handled_by"),
        "response": result.get("response"),
        "require_human": req.require_human,
        "human_feedback": result.get("human_feedback")
    }

# -----------------------------
# 2️⃣ /resume — Human Feedback 이어가기
# -----------------------------
@app.post("/resume")
def resume(req: ResumeRequest):
    print("\n🔄 /resume 호출됨")
    print(f"📨 요청: session_id={req.session_id}, feedback={req.human_feedback!r}")
    config = {"configurable": {"thread_id": req.session_id}}
    
    try:
        # ✅ 공식문서 방식: Command(resume=True)
        result = app.state.graph.invoke(Command(resume=True), config=config)
        print(f"📦 resume 결과: {result}")

        # resume 후에도 interrupt 발생 가능 (예: human_review_agent)
        if "__interrupt__" in result:
            interrupt_list = result["__interrupt__"]
            interrupt_msg = None
            if isinstance(interrupt_list, list) and interrupt_list:
                interrupt_obj = interrupt_list[0]
                interrupt_msg = getattr(interrupt_obj, "value", str(interrupt_obj))

            print(f"⏸ resume 중 interrupt 발생 → {interrupt_msg}")
            return {
                "session_id": req.session_id,
                "handled_by": result.get("handled_by", "unknown"),
                "response": interrupt_msg or "⚠️ 인간 피드백이 필요합니다.",
                "require_human": True,
                "human_feedback": req.human_feedback
            }

        print("✅ resume 정상 완료")
        return {
            "session_id": req.session_id,
            "response": result.get("response"),
            "human_feedback": result.get("human_feedback"),
            "handled_by": result.get("handled_by")
        }

    except Exception as e:
        import traceback
        print("❌ resume 실행 중 예외 발생!")
        traceback.print_exc()
        return {"session_id": req.session_id, "error": str(e)}
