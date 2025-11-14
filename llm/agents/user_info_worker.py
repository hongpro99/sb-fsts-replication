from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from typing import TypedDict, List, Optional

prompt = """
너는 사용자 정보를 조회하는 전문 에이전트다.

## 역할
1. UserInfo에서 다음 3가지 필드만 다룬다:
   - buy_trading_logic
   - sell_trading_logic
   - trading_bot_name

2. 사용자가 user_id 조회를 원하면:
   - get_user_info(user_id)를 MCP tool로 호출해라.
   - tool 결과를 읽고 요약된 assistant 메시지를 생성하라.
   - tool 결과는 반드시 state에 저장하여 이후 대화에서 재사용해라.

3. 사용자가 "그 봇의 잔고 알려줘"라고 말하면:
   - 바로 이전 조회에서 얻은 trading_bot_name을 사용해
     get_auto_trading_balance(trading_bot_name) tool을 호출한다.
   - 결과를 읽고 assistant 메시지를 생성한다.
   """
   
def make_user_info_worker(llm, tools):
    agent = create_agent(
        model=llm,
        tools=tools,   # [get_user_info, get_auto_trading_balance]
        system_prompt=prompt,
        name="user_info_worker",

        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "get_user_info": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    },
                    "get_auto_trading_balance": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ]
    )
    return agent   