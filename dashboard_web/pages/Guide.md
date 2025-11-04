# chat.py
1️⃣ 사용자가 입력
→ /agent_chat 호출 → LangGraph 실행
→ human_review_agent 도달 시 require_human=True로 반환

2️⃣ Streamlit이 피드백 입력 UI 표시

3️⃣ 사용자가 승인/수정 입력 후
→ /resume 호출 → 그래프가 resume()으로 이어감

4️⃣ RedisSaver가 세션별 상태를 저장하므로
→ 동일 session_id로 중단 지점부터 정확히 재개

