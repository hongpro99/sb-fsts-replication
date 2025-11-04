from typing import Dict, Any, Literal
from langgraph.types import Command
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os

load_dotenv()

#llm 설정
llm = AzureChatOpenAI(
    azure_deployment="gpt-4o-mini",
    azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
    api_version="2024-10-21",
    temperature=0
    )

prompt = ChatPromptTemplate.from_template(
    """
    당신은 주식 자동매매 및 시장 분석 시스템의 총괄 관리 에이전트입니다.
    사용자의 입력을 읽고, 아래 기준에 따라 어떤 전문 에이전트에게 작업을 전달할지 결정하세요.

    ---
    에이전트 분류 기준:

    1️**stock_agent**
       - 주식 종목 코드, 테마, 시장코드 관련 질문
       - 예: "삼성전자 종목 코드 알려줘", "삼성전자 테마 알려줘", "삼성전자에 대해 분석해줘" 

    2️**news_agent**
       - 주식 뉴스, 이슈, 공시, 감성 분석, 시황 요약 관련 요청
       - 예: "오늘 삼성전자 뉴스 요약", "반도체 업황이 어때?"

    3 **rag_agent**
       - 내부 문서나 보고서 기반의 질의응답
       - 예: "이전 리서치 문서에서 PER 기준이 뭐였지?", "내 투자전략 문서 요약해줘"

    4️ **technical_agent**
    - RSI, MACD, 볼린저밴드, MFI, EMA, SMA 등 기술적 분석 관련 요청
    - 예: "RSI 값 알려줘", "MACD 추세 해석해줘", "볼린저 밴드 상단 돌파했어?"
    
    5 **portfolio_agent**
       - 내 포트폴리오, 손익 요약, 리밸런싱, 비중조정 관련 질문
       - 예: "내 포트폴리오 수익률 알려줘", "이번 달 손익 요약", "내 잔고 알려줘"    
   
    ---
    ⚙️ 출력 형식:
    반드시 아래 중 하나만 짧게 답변하세요.
    - 'stock' (주식 관련)
    - 'news' (뉴스 관련)
    - 'rag'  (문서 기반 질의응답)
    - 'portfolio' (계좌 관련) 
    - 'technical'(보조지표 관련)
    
    사용자의 입력:
    {input}
    """
)

def supervisor_agent(state: Dict[str, Any]) -> Command[Literal["stock_agent", "news_agent", "rag_agent", "technical_agent", "portfolio_agent"]]:
    msg = prompt.format_messages(input = state['input'])
    decision = llm.invoke(msg).content.strip().lower()
    
    if "stock" in decision:
        goto = "stock_agent"
    elif "news" in decision:
        goto = "news_agent"
    elif "portfolio" in decision:
        goto = "portfolio_agent"
    elif "technical" in decision:
        goto = "technical_agent"
    elif "rag" in decision:
        goto = "rag_agent"        
    else:
        # fallback 기본값: portfolio_agent → rag_agent 보조 호출 가능
        goto = "portfolio_agent"
        
    # require_human 플래그를 상태에 같이 내려보냄 (API에서 제어)
    return Command(update={"task": state["input"], "require_human": state.get("require_human", False)}, goto=goto)    
    
