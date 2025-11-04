import uuid
from fastapi import FastAPI
from datetime import datetime
from datetime import date
import uvicorn
import os
from app.legacy.factory import create_auto_trading_stock
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

# 환경 변수 파일 로드
load_dotenv()

# 봇 토큰 가져오기
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 봇 프리픽스 설정 (명령어 앞에 붙는 문자열, 예: "!help")
BOT_PREFIX = "!"

# 봇 초기화
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True  # 서버 관련 이벤트 접근
intents.members = True  # 멤버 정보 접근 (Server Members Intent 활성화)
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

# 글로벌 변수로 AutoTradingStock 객체를 저장
auto_trading = None

# 봇 이벤트: 준비 완료
# @bot.event
# async def on_ready():
#     # 특정 채널에 메시지 보내기
#     channel_id = '1314162472235831336' #메시지를 보낼 채널 ID
#     channel = bot.get_channel(channel_id)
    
#     if channel:
#         channel.send("👋 안녕하세요! 저는 트레이딩 봇입니다.\n"
#                         "모의투자 또는 실전투자를 선택해 트레이딩을 시작하세요.\n"
#                         "명령어를 입력하거나 자세한 내용을 확인하려면 도움말을 참조하세요.")
#     else:
#         print("지정된 채널을 찾을 수 없습니다.")


# 명령어: 모의투자 여부 입력받기
@bot.command(name="select")
async def select_account(ctx):
    global auto_trading

    await ctx.send("📊 어떤 계좌를 사용하시겠습니까? (real/mock):")

    # 사용자의 응답을 기다림
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=30)  # 30초 대기
        user_choice = msg.content.strip().lower()

        if user_choice in ["real", "mock"]:
            auto_trading = create_auto_trading_stock(user_choice)
            account_type = "모의투자" if user_choice == "mock" else "실전투자"

            # 성공 메시지 및 인증 정보 디스코드로 전송
            await ctx.send(f"✅ {account_type} 계좌가 선택되었습니다.")
                # 생성된 객체의 계좌 정보를 디스코드로 전송
            auto_trading.send_account_info_to_discord()

        else:
            await ctx.send("⚠️ 잘못된 입력입니다. 'real' 또는 'mock'을 입력해주세요.")
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {e}")

# 잔고 조회 명령어
@bot.command(name="balance")
async def balance(ctx):
    """디스코드 명령어로 잔고 조회"""
    global auto_trading

    if auto_trading is None:
        await ctx.send("⚠️ AutoTradingStock 객체가 초기화되지 않았습니다. 'initialize_auto_trading()'을 실행해주세요.")
        return

    try:
        await ctx.send("🔄 잔고 정보를 조회 중입니다...")
        auto_trading.inquire_balance()
    except Exception as e:
        await ctx.send(f"❌ 잔고 조회 중 오류 발생: {e}")
        
@bot.command(name="trading_hours")
async def get_trading_hours(ctx):
    """
    주식 시장 거래 시간을 조회하고 디스코드 채널에 전달합니다.
    사용법: !trading_hours [국가코드]
    예: !trading_hours US
    """
    if auto_trading is None:
        await ctx.send("⚠️ AutoTradingStock 객체가 초기화되지 않았습니다. 'initialize_auto_trading()'을 실행해주세요.")
        return
    
    # 사용자 입력 필터링 함수
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        # 국가 코드 입력 요청
        await ctx.send("🌍 주식 시장 국가 코드를 입력해주세요 (예: US, KR, JP):")
        country_msg = await bot.wait_for("message", check=check, timeout=30)
        country_code = country_msg.content.strip().upper()

        auto_trading.get_trading_hours(country_code)

    except Exception as e:
        await ctx.send(f"❌ 거래 시간 조회 중 오류 발생: {e}")
    

                
# 명령어: 트레이딩 시뮬레이션 실행
@bot.command(name="simulate")
async def simulate_trading(ctx, symbol: str = None):
    global auto_trading

    if auto_trading is None:
        await ctx.send("⚠️ 먼저 'select' 명령어로 계좌를 선택해주세요.")
        return

    if symbol is None:
        await ctx.send("⚠️ 종목 코드를 입력해주세요. 예: `!simulate 035420`")
        return
    
    
    start_date = date(2023, 1, 1)
    end_date = date(2024, 1, 1)
    target_trade_value_krw = 1000000
    
    await ctx.send(f"{symbol}의 시세입니다. ")
    auto_trading.get_stock_quote(symbol)

    await ctx.send(f"📈 트레이딩 시뮬레이션을 시작합니다. 종목: {symbol}, 기간: {start_date} ~ {end_date}")

    try:
        # 트레이딩 시뮬레이션 실행
        simulation_plot, realized_pnl, current_pnl = auto_trading.simulate_trading(
            symbol, start_date, end_date, target_trade_value_krw
        )

        # 시뮬레이션 결과 출력
        await ctx.send(f"✅ 트레이딩 시뮬레이션 완료!\n"
                    f"총 실현 손익: {realized_pnl:.2f} KRW\n"
                    f"현재 잔고: {current_pnl:.2f} KRW")

        # 차트를 저장하고 디스코드에 업로드
        chart_path = f"{symbol}_trading_chart.png"
        simulation_plot[0].savefig(chart_path)
        simulation_plot[0].clf()  # 메모리 해제를 위해 차트 초기화
        await ctx.send(file=discord.File(chart_path))

    except Exception as e:
        await ctx.send(f"❌ 트레이딩 시뮬레이션 중 오류 발생: {e}")

@bot.command(name="order")
async def place_order(ctx):
    # 메시지 필터링 함수 정의
    if auto_trading is None:
        await ctx.send("⚠️ AutoTradingStock 객체가 초기화되지 않았습니다. 'initialize_auto_trading()'을 실행해주세요.")
        return
    
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        # 주문 종류 요청 및 응답 대기
        await ctx.send("📊 주문 종류를 선택해주세요 (매수/매도):")
        order_type_msg = await bot.wait_for("message", check=check)
        user_order_type = order_type_msg.content.strip().lower()

        # 주문 종류 매핑
        if user_order_type == "매수":
            order_type = "buy"
        elif user_order_type == "매도":
            order_type = "sell"
        else:
            await ctx.send("❌ 잘못된 주문 종류입니다. '매수' 또는 '매도'를 입력해주세요.")
            return

        # 종목 코드 요청 및 응답 대기
        await ctx.send("📄 종목 코드를 입력해주세요:")
        symbol_msg = await bot.wait_for("message", check=check)
        symbol = symbol_msg.content.strip()

        # 주문 수량 요청 및 응답 대기
        await ctx.send("🔢 주문 수량을 입력해주세요:")
        qty_msg = await bot.wait_for("message", check=check)
        qty_str = qty_msg.content.strip()

        # 주문 수량 검증
        if not qty_str.isdigit():
            await ctx.send("❌ 입력된 수량이 올바르지 않습니다. 숫자를 입력해주세요.")
            return
        qty = int(qty_str)

        # 주문 가격 요청 및 응답 대기
        await ctx.send("💰 주문 가격을 입력해주세요 (시장가로 주문하려면 '시장가'를 입력하세요):")
        price_msg = await bot.wait_for("message", check=check)
        price_input = price_msg.content.strip()

        # 가격 설정
        buy_price = None
        sell_price = None

        if price_input.lower() == "시장가":
            if order_type == "buy":
                buy_price = None
            elif order_type == "sell":
                sell_price = None
        elif price_input.isdigit():
            if order_type == "buy":
                buy_price = int(price_input)
            elif order_type == "sell":
                sell_price = int(price_input)
        else:
            await ctx.send("❌ 입력된 가격이 올바르지 않습니다. 숫자나 '시장가'를 입력해주세요.")
            return

        # 주문 실행
        await ctx.send(
            f"⏳ 주문을 실행 중입니다: 종목={symbol}, 수량={qty}, 매수 가격={buy_price if order_type == 'buy' else 'N/A'}, "
            f"매도 가격={sell_price if order_type == 'sell' else 'N/A'}, 종류={order_type}"
        )
        auto_trading.place_order(
            symbol, qty, buy_price=buy_price, sell_price=sell_price, order_type=order_type
        )
        await ctx.send(
            f"✅ 주문 완료: 종목={symbol}, 수량={qty}, 매수 가격={buy_price if order_type == 'buy' else 'N/A'}, "
            f"매도 가격={sell_price if order_type == 'sell' else 'N/A'}, 종류={order_type}"
        )
        #주문되었을때와 체결되었을 때를 나눠서 개발해야함!!(해야할 일)

    except Exception as e:
        await ctx.send(f"❌ 주문 처리 중 오류 발생: {e}")

@bot.command(name="volumeRanking_trading")
async def volumeRanking_trading(ctx):
    """
    시장별 거래량 순위 조회 명령어
    사용법: !volumeRanking_trading [시장코드]
    """
    global auto_trading

    if auto_trading is None:
        await ctx.send("⚠️ AutoTradingStock 객체가 초기화되지 않았습니다. 'initialize_auto_trading()'을 실행해주세요.")
        return
    
    # 사용자 입력 처리
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel
    
    try:

        await ctx.send("📊 입력 종목 코드를 입력해주세요 (0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200):")
        market_msg = await bot.wait_for("message", check=check, timeout=30)
        input_market = market_msg.content.strip().upper()
                
        # 거래량 순위 조회 실행
        await ctx.send(f"🔄 **{input_market}** 시장의 거래량 순위를 조회 중입니다...")
        auto_trading.get_volume_power_ranking_and_trade(input_market)

    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {e}")


@bot.command(name="dividend_ranking")
async def dividend_ranking(ctx):
    """
    배당률 상위 종목을 조회하고 디스코드에 전송하는 명령어
    사용법: !dividend_ranking
    """
    global auto_trading

    if auto_trading is None:
        await ctx.send("⚠️ 먼저 계좌를 선택해주세요. `!select` 명령어를 사용하세요.")
        return

    await ctx.send("🔄 배당률 상위 종목을 조회 중입니다...")
    try:
        auto_trading.get_top_dividend_stocks()

    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {e}")

# 외국인 순매수 시뮬레이션 명령어
@bot.command(name="foreign_simulate") #!foreign_simulate 005930 20230101 20231231
async def foreign_simulate(ctx, symbol: str, start_date: str, end_date: str):
    """
    외국인 순매수 시뮬레이션 명령어
    Args:
        ctx: 디스코드 명령어 컨텍스트
        symbol (str): 종목 코드
        start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
        end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
    """
    
    await ctx.send(f"📊 외국인 순매수 시뮬레이션을 시작합니다.\n"
                f"종목: {symbol}, 기간: {start_date} ~ {end_date}")

    try:
        # 외국인 순매수 데이터 가져오기
        data = auto_trading.fetch_foreign_investor_data(symbol, start_date, end_date)
        
        if not data:
            await ctx.send(f"⚠️ {symbol}에 대한 데이터가 없습니다. 다른 기간을 입력해주세요.")
            return

        # 시뮬레이션 수행
        await ctx.send("🔄 시뮬레이션을 실행 중입니다...")
        auto_trading.foreign_investor_simulate_trading(data)

    except Exception as e:
        await ctx.send(f"❌ 시뮬레이션 중 오류가 발생했습니다: {e}")
        
@bot.command(name="income_statement") #income_statement 005930
async def income_statement(ctx, symbol: str):
    if auto_trading is None:
        await ctx.send("⚠️ 먼저 계좌를 선택해주세요. `!select` 명령어를 사용하세요.")
        return

    try:
        await ctx.send(f"🔄 {symbol} 손익계산서를 조회 중입니다...")

        # 손익계산서 데이터 가져오기
        auto_trading.get_income_statement(symbol)
    except Exception as e:
        await ctx.send(f"❌ 손익계산서 조회 중 오류 발생: {e}")
        
# 투자자 매매 동향 명령어
@bot.command(name="investor_trend")
async def investor_trend(ctx):
    if auto_trading is None:
        await ctx.send("⚠️ 먼저 계좌를 선택해주세요. `!select` 명령어를 사용하세요.")
        return

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        await ctx.send("📊 시장 코드를 입력해주세요 (KSP: KOSPI, KSQ: KOSDAQ):")
        market_msg = await bot.wait_for("message", check=check, timeout=30)
        market_code = market_msg.content.strip().upper()

        await ctx.send("📊 업종 코드를 입력해주세요 (0001: KOSPI, 1001:KOSDAQ):")
        industry_msg = await bot.wait_for("message", check=check, timeout=30)
        industry_code = industry_msg.content.strip()

        auto_trading.get_investor_trend(market_code, industry_code)
        await ctx.send(f"✅ 투자자 매매 동향 조회를 완료했습니다.")
    except Exception as e:
        await ctx.send(f"❌ 투자자 매매 동향 조회 중 오류 발생: {e}")
        
        # RSI 시뮬레이션 명령어
@bot.command(name="rsi_simulate") #!rsi_simulate 005930 2023-01-01 2023-12-31
async def rsi_simulate(ctx, symbol: str, start_date: str, end_date: str):
    if auto_trading is None:
        await ctx.send("⚠️ 먼저 계좌를 선택해주세요. `!select` 명령어를 사용하세요.")
        return

    try:
        await ctx.send(f"📊 RSI 매매 시뮬레이션을 시작합니다. 종목: {symbol}, 기간: {start_date} ~ {end_date}")
        plot, _, _, final_assets, total_pnl = auto_trading.rsi_simulate_trading(symbol, start_date, end_date)

        # 결과 출력
        await ctx.send(f"✅ RSI 시뮬레이션 완료!\n최종 자산: {final_assets:.2f} KRW\n총 손익: {total_pnl:.2f} KRW")

        # 차트 업로드
        chart_path = f"{symbol}_rsi_simulation.png"
        plot.savefig(chart_path)
        await ctx.send(file=discord.File(chart_path))
        os.remove(chart_path)
    except Exception as e:
        await ctx.send(f"❌ RSI 시뮬레이션 중 오류 발생: {e}")
                        
# 봇 실행
if __name__ == "__main__":
    try:
        res = bot.run(DISCORD_BOT_TOKEN)
        print(res)
        
    except Exception as e:
        print(f"❌ 봇 실행 중 오류 발생: {e}")