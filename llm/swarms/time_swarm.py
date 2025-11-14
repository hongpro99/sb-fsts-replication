from langgraph_swarm import create_swarm, create_handoff_tool
from langgraph.checkpoint.redis import RedisSaver
from llm.agents.time_worker import time_agent


redis_saver = RedisSaver.from_conn_string("redis://127.0.0.1:6379/0")

handoff_to_time = create_handoff_tool(agent_name="time_agent")

time_swarm = create_swarm(
    [time_agent],
    default_active_agent="time_agent"
).compile(checkpointer=redis_saver)
