from typing import Dict, Any
from langgraph.types import Command
from langgraph.graph import END

def human_review_agent(state: Dict[str, Any]) -> Command:
    """
    API 환경에서는 보통 클라이언트 UI에서 승인/수정 입력을 받아
    resume(...)로 이어갑니다. 데모로는 승인된 것으로 처리.
    """
    feedback = state.get("human_feedback", "Approved ✅")
    return Command(update={"human_feedback": feedback}, goto=END)
