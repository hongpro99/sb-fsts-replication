from typing import Dict, Any
from langgraph.types import Command, interrupt
from langgraph.graph import END

def human_review_agent(state: Dict[str, Any]) -> Command:
    """
    Human-in-the-loop (후처리 검토용)
    - agent 실행 후 require_human=True인 경우 호출됨
    - 사람 피드백을 기다렸다가 /resume 입력 반영
    """
    print("\n🧩 [human_review_agent] 호출됨")
    print(f"📤 입력 state: {state}")
    
    if "human_feedback" not in state:
        return interrupt("🤔 AI 결과를 검토하고 피드백을 입력하세요. (예: 승인 / 다시 요약해줘)")

    feedback = state["human_feedback"].strip().lower()
    print(f"✅ human_feedback 수신됨: {feedback}")
    
    # 승인 → 종료
    if feedback in ["승인", "approve", "ok", "yes"]:
        update = {
            "human_feedback": feedback,
            "response": "✅ 사용자가 결과를 승인했습니다.",
            "handled_by": "human_review_agent",
        }
        return Command(update=update, goto=END)

    # 다시 실행 요청 → 이전 agent로 재실행
    elif feedback in ["다시", "재실행", "retry", "수정"]:
        prev_agent = state.get("handled_by", None)
        if prev_agent:
            update = {
                "human_feedback": feedback,
                "response": f"🔁 사용자가 '{prev_agent}' 재실행을 요청했습니다.",
                "handled_by": "human_review_agent",
            }
            return Command(update=update, goto=prev_agent)

    # 일반 피드백 기록 후 종료
    update = {
        "human_feedback": feedback,
        "response": f"📝 피드백이 기록되었습니다: '{feedback}'",
        "handled_by": "human_review_agent",
    }
    return Command(update=update, goto=END)
