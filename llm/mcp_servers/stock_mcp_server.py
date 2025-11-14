from mcp.server.fastmcp import FastMCP
from datetime import datetime
import pytz, re, feedparser, json, os
from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import pandas as pd
import argparse

from app.utils.dynamodb.model.user_info_model import UserInfo
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance
from app.utils.technical_indicator import TechnicalIndicator
from llm.rag.rag_qdrant import run_rag_pipeline
from app.utils.auto_trading_bot import AutoTradingBot
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8005")), help="Port number for MCP server")
args = parser.parse_args()

mcp = FastMCP("stock-server", port=args.port)

indicator = TechnicalIndicator()
id = 'id1'
auto_trading_bot = AutoTradingBot(id=id)
@mcp.tool()
def get_current_time() -> str:
    """Get current time in Asia/Seoul (YYYY-MM-DD HH:MM:SS)."""
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def get_stock_news_sentiment(stock_name: str) -> str:
    """
    뉴스 제목과 원문만 가져오는 MCP 도구.
    LLM 분석은 worker에서 수행한다.
    """
    rss_url = f"https://news.google.com/rss/search?q={stock_name}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)

    out = []
    for e in feed.entries[:5]:
        content = re.sub(r"<[^>]*>", "", e.summary or "")
        out.append({
            "title": e.title,
            "content": content
        })

    return json.dumps(out, ensure_ascii=False)

@mcp.tool()
def get_user_info(user_id: str) -> str:
    """
    UserInfo에서 필요한 3개 필드만 조회해서 반환한다:
    - buy_trading_logic (list[str])
    - sell_trading_logic (list[str])
    - trading_bot_name (str)
    """
    try:
        user = UserInfo.get(user_id)

        data = {
            "buy_trading_logic": user.buy_trading_logic,
            "sell_trading_logic": user.sell_trading_logic,
            "trading_bot_name": user.trading_bot_name
        }

        return json.dumps(data, ensure_ascii=False)

    except UserInfo.DoesNotExist:
        return json.dumps({"error": f"User '{user_id}' not found"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_stock_symbol(stock_name: str) -> str:
    """
    fsts-stock-symbol 테이블에서 종목 이름(stock_name)으로 기본 정보를 조회합니다.
    - stock_name: 종목 이름 (e.g., '삼성전자')
    """
    try:
        # 이름으로 scan
        items = StockSymbol.scan(StockSymbol.symbol_name == stock_name)

        result = []
        for item in items:
            result.append({k: str(v) for k, v in item.attribute_values.items()})

        if not result:
            return json.dumps({"error": f"Symbol name '{stock_name}' not found"}, ensure_ascii=False)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_auto_trading_balance(trading_bot_name: str) -> str:
    """
    Trading Bot 이름으로 전체 잔고 목록을 조회한다.
    """
    try:
        balances = AutoTradingBalance.query(trading_bot_name)

        result = []
        for item in balances:
            result.append(item.attribute_values)

        if not result:
            return json.dumps({"error": f"No balance found for bot '{trading_bot_name}'"}, ensure_ascii=False)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    
@mcp.tool()
def get_indicator(stock_name: str, indicator_type: str, start_date: str, end_date: str) -> str:
    """
    종목 이름 + 기간을 입력받아 OHLC와 모든 보조지표를 계산한 후
    원하는 indicator만 반환하는 MCP Tool.
    """
    try:
        # 1️⃣ 종목명 → 종목코드(symbol) 변환
        items = StockSymbol.scan(StockSymbol.symbol_name == stock_name)
        codes = [item.symbol for item in items]

        if not codes:
            return json.dumps({"error": f"Symbol name '{stock_name}' not found"}, ensure_ascii=False)

        symbol = codes[0]

        # 2️⃣ 네 기존 내부 함수 사용
        # _get_ohlc(symbol, start_date, end_date, interval, mode)
        ohlc_data = auto_trading_bot._get_ohlc(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        # 3️⃣ 모든 indicator가 계산된 df 생성
        df = auto_trading_bot._create_ohlc_df(
            ohlc_data=ohlc_data,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        # 4️⃣ 사용자가 요청한 indicator만 추출
        available = df.columns.tolist()

        mapping = {
            "rsi": ["Close", "rsi"],
            "macd": ["Close", "macd", "macd_signal", "macd_histogram"],
            "mfi": ["Close", "mfi"],
            "bollinger": ["Close", "BB_Upper", "BB_Middle", "BB_Lower"],
            "stochastic": ["Close", "stochastic_k", "stochastic_d"],
            "ema": [col for col in available if col.startswith("EMA_")],
            "sma": [col for col in available if col.startswith("SMA_")],
            "wma": [col for col in available if col.startswith("WMA_")],
        }

        if indicator_type not in mapping:
            return json.dumps({"error": f"Unsupported indicator type: {indicator_type}"}, ensure_ascii=False)

        cols = mapping[indicator_type]
        cols = [c for c in cols if c in available]  # 실제 존재하는 컬럼만 선택

        # 최근 5개만 반환
        result = df[cols].dropna().tail(5).to_dict(orient="records")

        return json.dumps({
            "symbol": symbol,
            "stock_name": stock_name,
            "indicator": indicator_type,
            "start_date": start_date,
            "end_date": end_date,
            "result": result
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def rag_search(query: str) -> str:
    return run_rag_pipeline(query)
    
if __name__ == "__main__":
    print("🚀 Starting MCP server at :8005 (SSE)")
    mcp.run(transport="sse")