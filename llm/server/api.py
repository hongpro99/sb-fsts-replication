# server/api.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel
import redis
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.redis import RedisSaver

from llm.agents.supervisor_agent import supervisor_agent
from llm.agents.stock_agent import stock_agent
from llm.agents.news_agent import news_agent
from llm.agents.human_review_agent import human_review_agent
from llm.agents.rag_agent import rag_agent
from llm.agents.portfolio_agent import portfolio_agent
from llm.agents.technical_agent import technical_agent

from llm.ingestion.local_index import build_or_update_index

# -----------------------------
# AppState 정의
# -----------------------------
from typing import TypedDict, Literal

class AppState(TypedDict, total=False):
    input: str
    task: str
    response: str
    handled_by: str
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
    session_id: str
    text: str
    require_human: bool = False

class ResumeRequest(BaseModel):
    session_id: str
    human_feedback: str

# -----------------------------
# 1️⃣ /agent_chat — 그래프 시작
# -----------------------------
@app.post("/agent_chat")
def agent_chat(req: ChatRequest):
    init_state = {"input": req.text, "require_human": req.require_human}
    result = app.state.graph.invoke(init_state, config={"thread_id": req.session_id})
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
    """
    Human-in-the-loop 재개 엔드포인트.
    LangGraph 체크포인트에서 이어서 실행.
    """
    result = app.state.graph.resume(
        {"human_feedback": req.human_feedback},
        config={"thread_id": req.session_id}
    )
    return {
        "session_id": req.session_id,
        "response": result.get("response"),
        "human_feedback": result.get("human_feedback"),
        "handled_by": result.get("handled_by")
    }
