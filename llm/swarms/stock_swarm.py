from langgraph_swarm import create_swarm, create_handoff_tool
from langgraph.checkpoint.redis import RedisSaver
from llm.agents.stock_agent import stock_agent
from llm.agents.news_agent import news_agent

redis_saver = RedisSaver.from_conn_string("redis://127.0.0.1:6379/0")

handoff_to_news = create_handoff_tool(agent_name="news_agent")
handoff_to_stock = create_handoff_tool(agent_name="stock_agent")

stock_swarm = create_swarm(
    [stock_agent, news_agent],
    default_active_agent="stock_agent"
).compile(checkpointer=redis_saver)
