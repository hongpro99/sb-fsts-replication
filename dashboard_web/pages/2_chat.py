import streamlit as st
import requests
import uuid

API_URL_CHAT = "http://localhost:7003/agent_chat"
API_URL_RESUME = "http://localhost:7003/resume"

st.set_page_config(page_title="AI Multi-Agent", layout="wide")

# --------------------------------------------------------------
# 1) 세션 초기화
# --------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = False

if "interrupt_message" not in st.session_state:
    st.session_state.interrupt_message = None


# --------------------------------------------------------------
# 2) 메시지 표시 함수
# --------------------------------------------------------------
def show_messages():
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            st.chat_message("user").write(content)
        else:
            st.chat_message("assistant").write(content)


# --------------------------------------------------------------
# 3) 서버와 통신 (agent_chat)
# --------------------------------------------------------------
def send_to_agent(user_text):
    payload = {
        "session_id": st.session_state.session_id,
        "text": user_text
    }

    response = requests.post(API_URL_CHAT, json=payload)
    return response.json()


# --------------------------------------------------------------
# 4) 서버와 통신 (resume)
# --------------------------------------------------------------
def send_resume(feedback_text):
    payload = {
        "session_id": st.session_state.session_id,
        "human_feedback": feedback_text
    }

    response = requests.post(API_URL_RESUME, json=payload)
    return response.json()


# --------------------------------------------------------------
# UI 구성
# --------------------------------------------------------------
st.title("🧠 Multi-Agent (Supervisor + Workers) with MCP & RAG")

show_messages()

# --------------------------------------------------------------
# 🔥 인터럽트 UI - 변경 후
# --------------------------------------------------------------
if st.session_state.pending_interrupt:
    st.warning("🛑 에이전트가 사람의 승인을 기다리고 있습니다.")

    interrupt_msg = st.session_state.interrupt_message
    st.info(interrupt_msg)

    st.write("### 작업을 어떻게 할까요?")

    col1, col2, col3 = st.columns(3)

    # 승인
    if col1.button("✔ 승인"):
        st.session_state.pending_interrupt = False
        result = send_resume("approve")
        ai_msg = result["response"]
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        st.rerun()

    # 거절
    if col2.button("❌ 거절"):
        st.session_state.pending_interrupt = False
        result = send_resume("reject")
        ai_msg = result["response"]
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        st.rerun()

    # 편집
    if col3.button("✏ 편집"):
        st.session_state.pending_interrupt = False
        result = send_resume("edit")
        ai_msg = result["response"]
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        st.rerun()

    st.stop()


# --------------------------------------------------------------
# 일반 입력 UI
# --------------------------------------------------------------
user_text = st.chat_input("메시지를 입력하세요")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})

    # 서버 전송
    data = send_to_agent(user_text)

    # interrupt 발생?
    if data.get("require_human"):
        st.session_state.pending_interrupt = True
        st.session_state.interrupt_message = data["response"]

        st.session_state.messages.append(
            {"role": "assistant", "content": data["response"]}
        )

        st.rerun()
        st.stop()

    # 일반 응답
    ai_msg = data.get("response", "")
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    st.rerun()
