# api.py
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.types import Command

# 🔄 Redis 대신 PostgresSaver (Async 버전) 사용
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import AzureChatOpenAI
import asyncio
from langgraph.prebuilt import ToolNode
from langchain_mcp_adapters.client import MultiServerMCPClient
# 🔹 Supervisor/Workers 그래프 빌더
from llm.supervisor.supervisor_workers import build_supervisor
import os 
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Stock AI (Supervisor/Workers) API")

# redis_cm = AsyncRedisSaver.from_conn_string("redis://127.0.0.1:6379")

# 🔐 Postgres 연결 정보 (dotenv 에서 가져오거나 기본값 사용)
DB_URI = os.getenv(
    "POSTGRES_DB_URI",
    "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable",
)

# 전역 Postgres Saver 컨텍스트 & 인스턴스 & 그래프
postgres_cm = AsyncPostgresSaver.from_conn_string(DB_URI)
checkpointer = None
supervisor_graph = None
llm = None
tools = None

# ==========================================================
# 🧩 요청 데이터 모델 정의
# ==========================================================
class ChatRequest(BaseModel):
    session_id: str
    text: str

class ResumeRequest(BaseModel):
    session_id: str
    human_feedback: str


# ==========================================
# FastAPI Startup 이벤트
# ==========================================
@app.on_event("startup")
async def startup_event():
    """
    MCP 서버 초기화 및 Supervisor 그래프 생성
    """
    global tools
    global llm
    global supervisor_graph
    global checkpointer

    print("🚀 MCP 서버 초기화 중...")

    # 여러 MCP 서버 등록
    client = MultiServerMCPClient(
        {
            "stock-server": {
                "url": "http://localhost:8005/sse",
                "transport": "sse",
                "timeout": 10.0,
                "sse_read_timeout": 300.0,
            },
            "tavily-mcp": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "tavily-mcp@0.1.4"],
                "env": {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY")},
            },
        }
    )

    # ✅ 모든 MCP 서버의 툴을 한 번에 로드
    tools = await client.get_tools()
    #['get_current_time', 'get_stock_news_sentiment', 'get_user_info', 'get_stock_symbol', 'get_auto_trading_balance', 'get_indicator', 'tavily-search', 'tavily-extract']
    print(f"✅ MCP Tools 로딩 완료: {[t.name for t in tools]}") 

    # ✅ ToolNode로 변환 (LangGraph에서 공용 허브로 사용)
    # tool_hub  = ToolNode(tools)

    # ✅ LangGraph LLM / Checkpointer 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0,
    )
    
    # ✅ PostgresSaver 초기화 (공식 문서 스타일)
    # from_conn_string 은 async context manager 이므로 __aenter__ 로 실제 saver 인스턴스 획득
    global postgres_cm
    checkpointer = await postgres_cm.__aenter__()

    # ⚠️ 첫 실행 시에만 테이블 생성/마이그레이션
    await checkpointer.setup()

    # ✅ Supervisor 그래프 빌드 (checkpointer = AsyncPostgresSaver)
    supervisor_graph = build_supervisor(llm=llm, tools=tools, checkpointer=checkpointer)
    print("✅ Supervisor/Workers 그래프 준비 완료 (PostgresSaver 사용)")


@app.on_event("shutdown")
async def shutdown_event():
    global postgres_cm
    if postgres_cm is not None:
        await postgres_cm.__aexit__(None, None, None)
    print("🛑 Shutdown complete — AsyncPostgresSaver closed.")

# ==========================================================
# 💬 /agent_chat — 메인 챗 엔드포인트
# ==========================================================
@app.post("/agent_chat")
async def agent_chat(req: ChatRequest):
    """
    사용자의 입력을 Supervisor 그래프에 전달하여 적절한 Worker를 호출.
    """
    assert supervisor_graph is not None, "Supervisor graph is not initialized"
    
    print(f"📨 입력: {req.text} (session={req.session_id})")

    config = {"configurable": {"thread_id": req.session_id}}
    payload = {"messages": [{"role": "user", "content": req.text}]}

    result = await supervisor_graph.ainvoke(payload, config)
    
    # Human-in-the-loop interrupt 처리
    interrupts = result.get("__interrupt__", [])
    print(f"interrupts: {interrupts}")
    if interrupts:
        msg = getattr(interrupts[0], "value", str(interrupts[0]))
        print(f"msg: {msg}")
        return {
            "session_id": req.session_id,
            "response": msg,
            "require_human": True
        }

    # 1) structured_response가 있으면 최우선 사용
    structured = result.get("structured_response") if isinstance(result, dict) else None
    if structured is not None:
        return {
            "session_id": req.session_id,
            "response": structured  # UI에서 그대로 보여주거나 필요하면 json.dumps(structured, ensure_ascii=False)
        }
        
    # ✅ 안전하게 content 추출
    response_text = (
        getattr(result, "response", None)
        or (
            result["messages"][-1].content
            if "messages" in result and result["messages"]
            else ""
        )
    )

    return {"session_id": req.session_id, "response": response_text}


# ==========================================================
# 🔁 /resume — Human Feedback 반영 후 재개
# ==========================================================
@app.post("/resume")
async def resume(req: ResumeRequest):
    """
    LangGraph interrupt 이후 사람 피드백을 Supervisor로 전달하여 실행 재개.
    """
    #assert supervisor_graph is not None, "Supervisor graph is not initialized"
    
    print(f"🔁 human_feedback: {req.human_feedback} (session={req.session_id})")

    
    config = {"configurable": {"thread_id": req.session_id}}
    
    '''LangGraph는 내부적으로:
    Checkpoint(thread_id=abc123)를 불러옵니다.
    직전 중단지점(ToolNode 실행 전)에서 상태를 복원합니다.
    사람 피드백(human_feedback)을 state에 주입합니다.
    ReAct 루프를 다시 진행시킵니다.
    '''
    
    # UI에서 온 문자열("approve", "reject", "edit")을
    # LangChain이 기대하는 decisions 포맷으로 변환
    decision_type = req.human_feedback
    decisions = [{"type": decision_type}]

    # async with AsyncRedisSaver.from_conn_string("redis://localhost:6379") as checkpointer:
    #     supervisor_graph = build_supervisor(llm=llm, tools=tools, checkpointer=checkpointer)
    #     result = await supervisor_graph.ainvoke(
    #         Command(resume={"decisions": decisions}),
    #         config=config
    #     )

    result = await supervisor_graph.ainvoke(
            Command(resume={"decisions": decisions}),
            config=config
        )
    
    interrupts = result.get("__interrupt__", [])
    print(f"[resume] interrupts: {interrupts}")

    if interrupts:
        msg = getattr(interrupts[0], "value", str(interrupts[0]))
        return {
            "session_id": req.session_id,
            "response": msg,
            "require_human": True
        }
    
    # ✅ 안전하게 content 추출
    response_text = (
        getattr(result, "response", None)
        or (
            result["messages"][-1].content
            if "messages" in result and result["messages"]
            else ""
        )
    )

    return {"session_id": req.session_id, "response": response_text}


# ==========================================================
# 🧭 Health Check
# ==========================================================
@app.get("/")
def root():
    return {"message": "✅ Stock AI (Supervisor/Workers) API is running"}
