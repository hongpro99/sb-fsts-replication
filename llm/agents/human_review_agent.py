from typing import Dict, Any
from langgraph.types import Command, interrupt
from langgraph.graph import END

def human_review_agent(state: Dict[str, Any]) -> Command:
    """
    Human-in-the-loop 노드:
    - 그래프 실행을 일시 중단(interrupt)
    - 사용자의 피드백 입력을 기다린 후 /resume으로 재개됨
    """
    if "human_feedback" not in state:
        # 처음 진입 시: 사용자 입력을 기다림
        return interrupt("Awaiting human feedback 📝")

    # /resume()으로 전달된 피드백이 있으면 반영 후 종료
    feedback = state["human_feedback"]
    return Command(update={"human_feedback": feedback}, goto=END)
