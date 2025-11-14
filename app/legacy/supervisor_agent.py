from typing import Dict, Any, Literal, List
from pydantic import BaseModel
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
from langgraph.graph import END

load_dotenv()

# ✅ 1. Structured output 정의
class AgentDecision(BaseModel):
    """LLM이 반환할 구조화된 판단 결과"""
    agent_type: List[Literal["stock", "news", "rag", "technical", "portfolio", "time"]] #다중 에이전트 판단 결과 구조
    reason: str
    
#llm 설정
llm = AzureChatOpenAI(
    azure_deployment="gpt-4o-mini",
    azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
    api_version="2024-10-21",
    temperature=0
    )

# 4️⃣ Structured Output 적용
structured_llm = llm.with_structured_output(AgentDecision)

# ✅ 3. 프롬프트 정의
prompt = ChatPromptTemplate.from_template(
    """
    당신은 주식 자동매매 및 시장 분석 시스템의 총괄 관리 에이전트입니다.
    사용자의 입력을 읽고, 어떤 전문 에이전트에게 작업을 전달할지 결정하세요.
    
    ---
    에이전트 분류 기준:

    1️ **stock** - 종목 코드, 테마, 시장 관련
    2️ **news** - 뉴스, 공시, 시황
    3️ **rag** - 내부 문서/리서치 질의응답
    4️ **technical** - RSI, MACD, EMA, SMA 등 기술적 분석
    5️ **portfolio** - 포트폴리오, 손익, 비중
    6️ **time** - 시간 관련 요청
    7️ **common** - 위의 분류에 해당하지 않거나 판단이 어려운 요청


    ---
    ⚙️ 출력 형식(JSON):
    {{
      "agent_type": "stock" | "news" | "rag" | "technical" | "portfolio" | "time" | "common",
      "reason": "이 선택을 한 이유를 간단히 설명"
    }}

    ---
    사용자의 입력:
    {input}
    """
)

def supervisor_agent(state: Dict[str, Any]) -> Command[Literal["stock_agent", "news_agent", "rag_agent", "technical_agent", "portfolio_agent", "time_agent", "common_agent"]]:
    
    """Supervisor Agent - LLM이 분기 결정하고, 사람 승인(interrupt) 후 다음 agent로 이동"""
    print("\n📘 [supervisor_agent] 호출됨")
    print(f"📤 입력 state: {state}")
    
    # LLM 호출 (structured output으로 결과 받기)
    msg = prompt.format_messages(input=state["input"])
    decision: AgentDecision = structured_llm.invoke(msg)

    # 에이전트 매핑
    goto_map = {
        "stock": "stock_agent",
        "news": "news_agent",
        "portfolio": "portfolio_agent",
        "technical": "technical_agent",
        "rag": "rag_agent",
        "time": "time_agent",
        "common" : "common_agent"
    }
    goto = goto_map.get(decision.agent_type, "common_agent") #뒤에는 default 값

    # 🔹 1단계: 사람 승인 interrupt 발생 (여기서 실행 중단)
    if "human_feedback" not in state:
        return interrupt(
            f"🧭 Supervisor 판단: '{goto}' 에이전트로 작업을 전달하려고 합니다.\n"
            f"질문: {state['input']}\n"
            "이 결정이 맞다면 '승인', 수정하려면 '거절'을 입력해주세요."
        )

    # 4️⃣ 승인 결과에 따라 분기 (resume 이후)
    # interrupt로 중단된 뒤, /resume 요청 시 state에 human_feedback이 들어옵니다.
    feedback = state.get("human_feedback", "").strip().lower() if "human_feedback" in state else ""
    print(f"✅ human_feedback 수신됨: {feedback}")
    
    # 승인된 경우 → 선택된 agent로 이동
    if feedback in ["승인", "approve", "ok", "yes"]:
        update = {
            "task": state["input"],
            "require_human": False,
            "handled_by": "supervisor_agent",
            "approval": feedback,
        }
        print(f"➡ 승인됨 → 다음 agent로 이동: {goto}")
        return Command(update=update, goto=goto)
    
    # 거절된 경우 → 종료
    elif feedback in ["거절", "no", "reject", "취소"]:
        update = {
            "handled_by": "supervisor_agent",
            "response": "❌ 사람이 판단을 거절했습니다. 그래프를 종료합니다.",
            "approval": feedback,
        }
        print("🚫 거절됨 → 그래프 종료")
        return Command(update=update, goto=END)
    
    print("⚠️ human_feedback이 유효하지 않음 → 그대로 종료")
    return Command(update={"handled_by": "supervisor_agent"}, goto=END)
                    
    
    
