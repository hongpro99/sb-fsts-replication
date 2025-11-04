import streamlit as st
import requests
import uuid

st.title("💹 Stock Assistant (LangGraph + /resume)")

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

AGENT_URL = "http://localhost:7003/agent_chat"
RESUME_URL = "http://localhost:7003/resume"

# 대화 로그 출력
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 사용자 입력
if prompt := st.chat_input("메시지를 입력하세요..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("응답 생성 중..."):
            try:
                res = requests.post(
                    AGENT_URL,
                    json={"session_id": st.session_state["session_id"], "text": prompt, "require_human": True},
                    timeout=90
                )
                res.raise_for_status()
                data = res.json()
                reply = data.get("response", "(응답 없음)")
            except Exception as e:
                reply = f"⚠️ 서버 오류: {e}"

            st.session_state["messages"].append({"role": "assistant", "content": reply})
            st.markdown(reply)

            # 👇 Human Review 필요 시 별도 입력창 표시
            if data.get("require_human"):
                feedback = st.text_input("🤔 AI 결과를 검토하고 피드백을 입력하세요:")
                if st.button("✅ 피드백 전송"):
                    try:
                        resume_res = requests.post(
                            RESUME_URL,
                            json={
                                "session_id": st.session_state["session_id"],
                                "human_feedback": feedback
                            },
                            timeout=90
                        )
                        resume_res.raise_for_status()
                        resume_data = resume_res.json()
                        final_reply = resume_data.get("response", "(재응답 없음)")
                        st.session_state["messages"].append({"role": "assistant", "content": final_reply})
                        st.markdown(final_reply)
                    except Exception as e:
                        st.error(f"Resume 요청 실패: {e}")
