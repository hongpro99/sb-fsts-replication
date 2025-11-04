# redis_client.py
import redis
import json

redis_client = redis.StrictRedis(
    host="localhost", port=6379, db=0, decode_responses=True
)

def save_state(session_id: str, state: dict):
    redis_client.set(session_id, json.dumps(state))

def load_state(session_id: str) -> dict:
    data = redis_client.get(session_id)
    return json.loads(data) if data else {"messages": [], "answer": ""}

def clear_state(session_id: str):
    redis_client.delete(session_id)

def serialize_state(result: dict):
    """LangGraph result를 JSON 직렬화 가능한 dict로 변환"""
    serializable = {}
    for k, v in result.items():
        if k == "messages":
            serializable["messages"] = []
            for m in v:
                # LangChain Message 객체 → dict 변환
                if hasattr(m, "type"):
                    serializable["messages"].append({
                        "type": m.type,
                        "role": getattr(m, "role", None),
                        "content": getattr(m, "content", None),
                        "name": getattr(m, "name", None),
                    })
                elif isinstance(m, dict):
                    serializable["messages"].append(m)
                else:
                    serializable["messages"].append({"content": str(m)})
        else:
            serializable[k] = v
    return serializable

