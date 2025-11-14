from langgraph_swarm import create_swarm, create_handoff_tool
from langgraph.checkpoint.redis import RedisSaver
from llm.agents.common_agent import common_agent


redis_saver = RedisSaver.from_conn_string("redis://127.0.0.1:6379/0")

handoff_to_time = create_handoff_tool(agent_name="common_agent")

common_swarm = create_swarm(
    [common_agent],
    default_active_agent="common_agent"
).compile(checkpointer=redis_saver)
