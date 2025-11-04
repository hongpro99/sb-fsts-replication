# mcp_server.py
from typing import List
from mcp.server.fastmcp import FastMCP
import pytz
from datetime import datetime, date
import argparse
from collections import Counter
import re
import feedparser
import os

# (옵션) Azure OpenAI 사용 시
from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from app import *

from app.utils.dynamodb.model.user_info_model import UserInfo
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance


print("AZURE_OPENAI_API_KEY =", bool(os.getenv("AZURE_OPENAI_API_KEY")))
print("OPENAI_API_KEY =", bool(os.getenv("OPENAI_API_KEY")))

# -----------------------------
# CLI 옵션: 포트 지정
# -----------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8005")), help="Port number for MCP server")
args = parser.parse_args()

# -----------------------------
# FastMCP 초기화 (SSE 트랜스포트)
# -----------------------------
mcp = FastMCP("stock-helpers", port=args.port)
# -----------------------------
# 간단 툴 1: 현재 시간 (Asia/Seoul)
# -----------------------------
@mcp.tool()
async def get_current_time() -> str:
    """Get current time in Asia/Seoul (YYYY-MM-DD HH:MM:SS)."""
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime("%Y-%m-%d %H:%M:%S")

# -----------------------------
# 간단 툴 2: 데모 날씨
# -----------------------------
@mcp.tool()
async def get_weather(location: str) -> str:
    """Demo weather for a location (placeholder)."""
    return f"Weather for {location}: sunny (demo)"

# -----------------------------
# 뉴스 감성/투자 의견 툴
# -----------------------------
def _make_llm():
    return ChatOpenAI(
        model="gpt-5-nano",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0
    )

@mcp.tool()
async def get_stock_news_sentiment(stock_name: str, only_today: bool) -> str:
    """
    주식 관련 뉴스를 조회하고 요약/감성/투자 의견을 반환합니다.
    - stock_name: 종목명(검색어)
    - only_today: 오늘 뉴스만 필터링 여부
    """
    llm = _make_llm()
    news_list = get_stock_news(stock_name, only_today=only_today)

    # 뉴스 요약 + 감성
    summarized_texts: List[str] = []
    for news in news_list:
        summary = summarize_news_with_gpt(llm, news["title"], news["summary"])
        sentiment = extract_sentiment(summary)
        summarized_texts.append(f"- {news['title']}\n{summary}\n(감성: {sentiment})")

    # 투자 의견
    opinion = generate_investment_opinion(llm, "\n\n".join(summarized_texts), stock_name)
    return opinion

# -----------------------------
# 내부 유틸 (RSS → 요약/감성 → 투자 의견)
# -----------------------------
def get_stock_news(query: str, max_results: int = 10, only_today: bool = False):
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    items = []

    for entry in feed.entries:
        # 요약에서 HTML 제거
        summary_cleaned = re.sub('<[^<]+?>', '', entry.summary or "")
        try:
            published_dt = datetime(*entry.published_parsed[:6])
            published_str = published_dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            published_dt = None
            published_str = "날짜 정보 없음"

        items.append({
            "title": entry.title,
            "link": entry.link,
            "summary": summary_cleaned,
            "published": published_str,
            "published_dt": published_dt
        })

    if only_today:
        today = date.today()
        items = [x for x in items if x["published_dt"] and x["published_dt"].date() == today]

    items.sort(key=lambda x: x["published_dt"] or datetime.min, reverse=True)
    return items[:max_results]

def summarize_news_with_gpt(llm, title: str, content: str) -> str:
    prompt = f"""
다음은 주식 관련 뉴스입니다:

제목: {title}
내용: {content}

1) 한 문단 요약
2) 감성(긍정/부정/중립) 판정
3) 근거 한 줄

형식:
[요약]
...
[감성]
긍정/부정/중립
[이유]
...
"""
    chain = llm | StrOutputParser()
    messages = [("system", "당신은 주식 분석 전문가입니다."), ("human", prompt)]
    return chain.invoke(messages)

def extract_sentiment(text: str) -> str:
    m = re.search(r"\[감성\]\s*(긍정|부정|중립)", text)
    return m.group(1) if m else "분류 실패"

def generate_investment_opinion(llm, news_summaries: str, stock_name: str) -> str:
    prompt = f"""
당신은 투자 전문가입니다.
아래는 '{stock_name}' 관련 뉴스 요약/감성입니다:

{news_summaries}

[투자 의견]
- 매수 고려 / 관망 / 리스크 주의 중 택 1
- 이유 2~3줄
"""
    chain = llm | StrOutputParser()
    messages = [("system", "간결하고 근거 있는 의견만"), ("human", prompt)]
    return chain.invoke(messages)

@mcp.tool()
async def get_user_info(user_id: str) -> str:
    """
    fsts-user-info DynamoDB 테이블에서 특정 사용자 정보를 조회합니다.
    - user_id: UserInfo의 hash_key (id)
    """
    try:
        user = UserInfo.get(user_id)
        data = {k: str(v) for k, v in user.attribute_values.items()}
        return f"[UserInfo]\n{data}"
    except UserInfo.DoesNotExist:
        return f"❌ User '{user_id}' not found"
    except Exception as e:
        return f"⚠️ Error fetching user info: {e}"

@mcp.tool()
async def get_stock_symbol(symbol: str) -> str:
    """
    fsts-stock-symbol 테이블에서 특정 종목(symbol)의 기본 정보를 조회합니다.
    - symbol: 종목 코드 (e.g., '005930')
    """
    try:
        item = StockSymbol.get(symbol)
        data = {k: str(v) for k, v in item.attribute_values.items()}
        return f"[StockSymbol]\n{data}"
    except StockSymbol.DoesNotExist:
        return f"❌ Symbol '{symbol}' not found"
    except Exception as e:
        return f"⚠️ Error fetching stock symbol: {e}"

@mcp.tool()
async def get_auto_trading_balance(trading_bot_name: str, symbol: str) -> str:
    """
    fsts-auto-trading-balance 테이블에서 특정 봇 + 종목 잔고 정보를 조회합니다.
    - trading_bot_name: 트레이딩 봇 이름 (hash key)
    - symbol: 종목 코드 (range key)
    """
    try:
        balance = AutoTradingBalance.get(trading_bot_name, symbol)
        data = {k: str(v) for k, v in balance.attribute_values.items()}
        return f"[AutoTradingBalance]\n{data}"
    except AutoTradingBalance.DoesNotExist:
        return f"❌ No balance found for bot={trading_bot_name}, symbol={symbol}"
    except Exception as e:
        return f"⚠️ Error fetching trading balance: {e}"
    
@mcp.tool()
async def get_stock_indicators_today(
    stock_query: str,
    user_id: str = "id1",
    rsi_period: int = 25,
    interval: str = "day"
) -> str:
    """
    종목의 오늘자(가장 최근 OHLC) 기준 모든 지표를 계산하여 반환합니다.
    """
    try:
        from app.utils.dynamodb.model.stock_symbol_model import StockSymbol
        from app.utils.auto_trading_bot import AutoTradingBot
        import pandas as pd
        from datetime import datetime, timedelta
        import json

        # 종목코드 확인
        if stock_query.isdigit():
            symbol = stock_query
            stock_name = StockSymbol.get(symbol).symbol_name
        else:
            result = list(StockSymbol.scan(filter_condition=(StockSymbol.symbol_name == stock_query)))
            if not result:
                return f"❌ '{stock_query}' 종목을 찾을 수 없습니다."
            symbol = result[0].symbol
            stock_name = result[0].symbol_name

        bot = AutoTradingBot(id=user_id, virtual=False)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=120)
        ohlc_data = bot._get_ohlc(symbol, start_date, end_date, interval=interval)
        df = bot._create_ohlc_df(ohlc_data, symbol, start_date, end_date, rsi_period=rsi_period)

        latest = df.iloc[-1]
        snapshot = {
            col: (None if pd.isna(latest[col]) else round(float(latest[col]), 4) if isinstance(latest[col], (int, float)) else str(latest[col]))
            for col in df.columns
        }

        return json.dumps({
            "stock_name": stock_name,
            "symbol": symbol,
            "as_of": str(latest.name),
            "today_indicators": snapshot
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"⚠️ Error in get_stock_indicators_today: {e}"

@mcp.tool()
async def get_stock_indicators_range(
    stock_query: str,
    user_id: str = "id1",
    start_date: str = None,
    end_date: str = None,
    rsi_period: int = 25,
    interval: str = "day"
) -> str:
    """
    특정 기간(start_date~end_date) 동안의 모든 지표값을 반환합니다.
    - 날짜 형식: YYYY-MM-DD
    """
    try:
        from app.utils.dynamodb.model.stock_symbol_model import StockSymbol
        from app.utils.auto_trading_bot import AutoTradingBot
        import pandas as pd
        from datetime import datetime, timedelta
        import json

        # 종목 코드 해석
        if stock_query.isdigit():
            symbol = stock_query
            stock_name = StockSymbol.get(symbol).symbol_name
        else:
            result = list(StockSymbol.scan(filter_condition=(StockSymbol.symbol_name == stock_query)))
            if not result:
                return f"❌ '{stock_query}' 종목을 찾을 수 없습니다."
            symbol = result[0].symbol
            stock_name = result[0].symbol_name

        # 기간 처리
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_date = datetime.now()
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_date = end_date - timedelta(days=180)

        bot = AutoTradingBot(id=user_id, virtual=False)
        ohlc_data = bot._get_ohlc(symbol, start_date, end_date, interval=interval)
        df = bot._create_ohlc_df(ohlc_data, symbol, start_date, end_date, rsi_period=rsi_period)

        # 결과 JSON 변환
        df_reset = df.reset_index()
        df_reset["Date"] = df_reset["Date"].astype(str)
        result_json = df_reset.to_dict(orient="records")

        return json.dumps({
            "stock_name": stock_name,
            "symbol": symbol,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "data_points": len(result_json),
            "indicators": result_json
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"⚠️ Error in get_stock_indicators_range: {e}"

# -----------------------------
# 서버 시작 (SSE)
# -----------------------------
if __name__ == "__main__":
    # LangGraph/Agent 쪽에서 SSE로 구독하므로 transport="sse"
    mcp.run(transport="sse")
