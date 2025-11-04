from mcp.server.fastmcp import FastMCP
from datetime import datetime
import pytz, re, feedparser, json, os
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import argparse

from app.utils.dynamodb.model.user_info_model import UserInfo
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8005")), help="Port number for MCP server")
args = parser.parse_args()

mcp = FastMCP("stock-server", port=args.port)

@mcp.tool()
async def get_current_time() -> str:
    """Get current time in Asia/Seoul (YYYY-MM-DD HH:MM:SS)."""
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
async def get_stock_news_sentiment(stock_name: str, only_today: bool = True) -> str:
    """뉴스 요약/감성(간단 데모)."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    rss_url = f"https://news.google.com/rss/search?q={stock_name}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    out = []
    for e in feed.entries[:5]:
        content = re.sub(r"<[^>]*>", "", e.summary or "")
        prompt = f"제목: {e.title}\n내용: {content}\n요약과 감성(긍정/부정/중립)을 한 문단으로."
        chain = llm | StrOutputParser()
        summary = chain.invoke([("system", "금융 분석 전문가"), ("human", prompt)])
        out.append({"title": e.title, "summary": summary})
    return json.dumps(out, ensure_ascii=False, indent=2)

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

    
if __name__ == "__main__":
    print("🚀 Starting MCP server at :8005 (SSE)")
    mcp.run(transport="sse")