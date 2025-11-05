import streamlit as st
import requests
import uuid

st.title("💹 Stock Assistant (LangGraph + /resume)")

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4()) #무작위 생성

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
                    json={"session_id": st.session_state["session_id"],
                            "text": prompt,
                            "require_human": True
                        },
                    timeout=90
                )
                res.raise_for_status()
                data = res.json()
                response = data.get("response", "(응답 없음)")
                print(f"response: {response}")
            except Exception as e:
                response = f"⚠️ 서버 오류: {e}"

            st.session_state["messages"].append({"role": "assistant", "content": response})
            st.markdown(response)

# -----------------------------
# interrupt 또는 require_human 처리
# -----------------------------
if st.session_state.get("messages"):
    last_msg = st.session_state["messages"][-1].get("content", "")

    if last_msg and (
        "에이전트로 작업을 전달하려고 합니다" in last_msg
        or "승인하시겠습니까" in last_msg
    ):
        st.warning("⚙️ Supervisor 승인 요청 감지됨")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 승인"):
                try:
                    resume_res = requests.post(
                        RESUME_URL,
                        json={
                            "session_id": st.session_state["session_id"],
                            "human_feedback": "승인"
                        },
                        timeout=90
                    )
                    resume_data = resume_res.json()
                    response = resume_data.get("response", "(승인 후 응답 없음)")
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    st.rerun()
                except Exception as e:
                    st.error(f"Resume 승인 실패: {e}")
        with col2:
            if st.button("❌ 거절"):
                try:
                    resume_res = requests.post(
                        RESUME_URL,
                        json={
                            "session_id": st.session_state["session_id"],
                            "human_feedback": "거절"
                        },
                        timeout=90
                    )
                    resume_data = resume_res.json()
                    response = resume_data.get("response", "(거절 후 응답 없음)")
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    st.rerun()
                except Exception as e:
                    st.error(f"Resume 거절 실패: {e}")

    else:
        st.markdown("### 💬 결과 피드백")
        feedback = st.text_input("AI 결과를 검토하고 피드백을 입력하세요:", key="feedback_input")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ 승인", key="approve_btn"):
                try:
                    resume_res = requests.post(
                        RESUME_URL,
                        json={
                            "session_id": st.session_state["session_id"],
                            "human_feedback": "승인"
                        },
                        timeout=90
                    )
                    resume_data = resume_res.json()
                    final_response = resume_data.get("response", "(재응답 없음)")
                    st.session_state["messages"].append({"role": "assistant", "content": final_response})
                    st.rerun()
                except Exception as e:
                    st.error(f"Resume 승인 실패: {e}")
        with c2:
            if st.button("✏️ 피드백 전송", key="feedback_btn"):
                try:
                    resume_res = requests.post(
                        RESUME_URL,
                        json={
                            "session_id": st.session_state["session_id"],
                            "human_feedback": feedback or "다시 요약해줘"
                        },
                        timeout=90
                    )
                    resume_data = resume_res.json()
                    final_response = resume_data.get("response", "(재응답 없음)")
                    st.session_state["messages"].append({"role": "assistant", "content": final_response})
                    st.rerun()
                except Exception as e:
                    st.error(f"Resume 피드백 실패: {e}")
