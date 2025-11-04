from datetime import datetime, date, timedelta
from pytz import timezone
import requests
import json
import math

from app.utils.database import get_db, get_db_session
from app.utils.crud_sql import SQLExecutor
from app.utils.auto_trading_bot import AutoTradingBot
from app.utils.dynamodb.crud import DynamoDBExecutor
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol, StockSymbol2
from app.utils.dynamodb.model.user_info_model import UserInfo
from pykis import KisBalance
from app.utils.webhook import Webhook
# db = get_db()
sql_executor = SQLExecutor()
#보조지표 클래스
webhook = Webhook()

def scheduled_trading_schedulerbot_task():
    scheduled_trading(id='schedulerbot', virtual= False, trading_bot_name = 'schedulerbot')

# def scheduled_trading_id1_task():
#     scheduled_trading(id="id1")

def scheduled_trading_dreaminmindbot_task():
    scheduled_trading(id='id1', virtual = False, trading_bot_name = 'dreaminmindbot')

def scheduled_trading_bnuazz15bot_task():
    scheduled_trading(id='bnuazz15', virtual = True, trading_bot_name = 'bnuazz15bot')
    
def scheduled_trading_weeklybot_task():
    scheduled_trading(id='weeklybot', virtual = True, trading_bot_name = 'weeklybot')
    
def scheduled_trading_bnuazz15bot_real_task():
    scheduled_trading(id='bnuazz15bot_real', virtual = False, trading_bot_name = 'bnuazz15bot_real')
    
def get_netbuy_summary_by_investor():
    netbuy_summary_by_investor(id='bnuazz15bot_real', virtual = False, trading_bot_name = 'bnuazz15bot_real')


def scheduled_trading(id, virtual = False, trading_bot_name = 'schedulerbot', sorting = 'trade_volume'):
    
    # TO-DO
    # 잔고 조회 여기에 추가
    trading_bot = AutoTradingBot(id=id, virtual=virtual)
    print(f"{trading_bot_name}의 자동 트레이딩을 시작합니다")

    # 당일로부터 1년전 기간으로 차트 분석
    end_date = date.today()
    start_date = end_date
    interval = "day"
    
    # ✅ 코스닥150 종목 가져오기
    result = list(StockSymbol.scan(
        filter_condition=(StockSymbol.type == 'kosdaq150')
    ))

    # ✅ 거래대금 기준 정렬 함수
    def get_estimated_trade_value(stock):
        try:
            
            symbol = stock.symbol

            # OHLC 데이터 가져오기 (최신 종가용)
            ohlc_data = trading_bot._get_ohlc(symbol, start_date, end_date, interval)
            if not ohlc_data:
                print(f"❌ {symbol} OHLC 데이터 없음")
                return -1

            # 가장 마지막 종가
            last_candle = ohlc_data[-1]
            close_price = last_candle.close

            # 외국인+기관 순매수 기반 거래대금 계산
            trade_value = trading_bot.calculate_trade_value_from_fake_qty(
                api_response=None,  # 내부에서 API 호출함
                close_price=close_price,
                symbol=symbol
            )

            print(f"📊 {stock.symbol_name} | 종가: {close_price:,} | 예상 거래대금: {trade_value:,}원")
            return trade_value
        except Exception as e:
            print(f"❌ {stock.symbol} 거래대금 계산 실패: {e}")
            return -1

    if sorting == 'trade_volume':
        # ✅ 거래대금 기준 내림차순 정렬
        sorted_symbols = sorted(
            result,
            key=lambda stock: get_estimated_trade_value(stock),
            reverse=True
        )
    else:
        sorted_symbols = result

    print(f"sorted_result : {sorted_symbols}")
    
    # 매수 목표 거래 금액
    trading_bot_name = trading_bot_name
    user_info = list(UserInfo.query(id))[0]

    buy_trading_logic = user_info.buy_trading_logic
    sell_trading_logic = user_info.sell_trading_logic
    target_trade_value_krw = user_info.target_trade_value_krw
    max_allocation = user_info.max_allocation
    interval = user_info.interval
    min_trade_value = user_info.min_trade_value
    target_trade_value_ratio = user_info.target_trade_value_ratio
    
    if user_info.take_profit_logic['use_yn'] is True:
        take_profit_logic = user_info.take_profit_logic
    else:
        # 익절 로직이 사용되지 않는 경우 None으로 설정
        take_profit_logic = None
    
    if user_info.stop_loss_logic['use_yn'] is True:
        stop_loss_logic = user_info.stop_loss_logic
    else:
        # 손절 로직이 사용되지 않는 경우 None으로 설정
        stop_loss_logic = None

    # ✅ scheduled_trading 시작 시 잔고 조회
    account = trading_bot.kis.account()
    balance: KisBalance = account.balance()
    
    print(f'------ {trading_bot_name}의 계좌 익절/손절이 완료되었습니다. 이제부터 주식 자동 트레이딩을 시작합니다!')            
    webhook.send_discord_webhook(
    f'----------------------- {trading_bot_name}의 계좌 익절/손절이 완료되었습니다. 이제부터 주식 자동 트레이딩을 시작합니다!',
    "trading"
    )

    trading_bot.trade(
        trading_bot_name=trading_bot_name,
        buy_trading_logic=buy_trading_logic,
        sell_trading_logic=sell_trading_logic,
        selected_symbols=sorted_symbols,
        start_date=start_date,
        end_date=end_date,
        target_trade_value_krw=target_trade_value_krw,
        target_trade_value_ratio=target_trade_value_ratio,
        min_trade_value=min_trade_value,
        interval=interval,
        max_allocation = max_allocation,
        rsi_period=25,
        take_profit_logic=take_profit_logic,
        stop_loss_logic=stop_loss_logic, 
    )

    #✅ enumerate로 종목 번호 부여 (1부터 시작)
    # for i, stock in enumerate(sorted_symbols, start=1):
    #     symbol = stock.symbol
    #     symbol_name = stock.symbol_name

    #     max_retries = 5
    #     retries = 0

    #     print(f'------ {trading_bot_name}의 {symbol_name} 주식 자동 트레이딩을 시작합니다. ------')
        
    #     take_profit_logic = {
    #         "name": "fixed_ratio",
    #         "params": {
    #             "ratio": 5
    #         }
    #     }

    #     stop_loss_logic = {
    #         "name": "fixed_ratio",
    #         "params": {
    #             "ratio": 5
    #         }
    #     }

    #     target_trade_value_ratio = 20 # 임시

    #     while retries < max_retries:
    #         try:
    #             trading_bot.trade(
    #                 trading_bot_name=trading_bot_name,
    #                 buy_trading_logic=buy_trading_logic,
    #                 sell_trading_logic=sell_trading_logic,
    #                 symbol=symbol,
    #                 symbol_name=symbol_name,
    #                 start_date=start_date,
    #                 end_date=end_date,
    #                 target_trade_value_krw=target_trade_value_krw,
    #                 target_trade_value_ratio=target_trade_value_ratio,
    #                 interval=interval,
    #                 max_allocation = max_allocation,
    #                 take_profit_logic=take_profit_logic,
    #                 stop_loss_logic=stop_loss_logic, 
    #             )
    #             break
    #         except Exception as e:
    #             retries += 1
    #             print(f"Error occurred while trading {symbol_name} (Attempt {retries}/{max_retries}): {e}")
    #             if retries >= max_retries:
    #                 print(f"Skipping {symbol_name} after {max_retries} failed attempts.")
                    
    trading_bot._upsert_account_balance(trading_bot_name) # 따로 스케줄러 만들어서 다른 시간에 하도록 설정해도 됨
    trading_bot.update_roi(trading_bot_name) # 따로 스케줄러 만들어서 다른 시간에 하도록 설정해도 됨

def run_market_netbuy_summary():
    
    trading_bot = AutoTradingBot(id='bnuazz15bot_real', virtual=False)
    
    result_kospi = trading_bot.get_foreign_institution_net_buy_summary(market_code= 'KSP', industry="0001")
    result_kosdaq = trading_bot.get_foreign_institution_net_buy_summary(market_code='KSQ', industry='1001')
    
    # 메시지 포맷팅
    def format_result(title, result):
        if not result:
            return f"❌ {title} 조회 실패 또는 데이터 없음"
        lines = [f"✅ {title}"]
        for name, amount in result.items():
            lines.append(f"• {name}: {int(amount):,} 원")
        return "\n".join(lines)

    message = "\n\n".join([
        format_result("📈 KOSPI 외국인/기관 순매수", result_kospi),
        format_result("📊 KOSDAQ 외국인/기관 순매수", result_kosdaq)

    ])

    # 디스코드 전송
    webhook.send_discord_webhook(message, "alarm")
    
def netbuy_summary_by_investor(id, virtual, trading_bot_name):
    
    # 1. 트레이딩 봇 초기화
    trading_bot = AutoTradingBot(id=id, virtual=virtual)

    # 2. 날짜 설정 (당일)
    today = date.today()
    interval = "day"
    
    # ✅ symbol → symbol_name 매핑
    symbol_name_map = {}
    for item in StockSymbol.scan():
        symbol_name_map[item.symbol] = item.symbol_name
    for item in StockSymbol2.scan():
        if item.symbol not in symbol_name_map:
            symbol_name_map[item.symbol] = item.symbol_name

    # 3. 계좌 잔고 조회
    kis_account = trading_bot.kis.account()
    kis_balance: KisBalance = kis_account.balance()

    # 4. 보유 종목 필터링 (수량 > 0)
    non_zero_stocks = [stock for stock in kis_balance.stocks if stock.qty > 0]
    if not non_zero_stocks:
        print("❌ 보유 종목이 없습니다.")
        return

    kis_balance.stocks = non_zero_stocks

    # 5. 알림 시작 메시지
    webhook.send_discord_webhook(
        f'📢 **[{trading_bot_name}] 보유 종목별 외인/기관 매수 추정**\n', "alarm"
    )

    # 6. 종목별 외인/기관 데이터 출력
    for stock in kis_balance.stocks:
        symbol = stock.symbol

        # OHLC 데이터 가져오기
        ohlc_data = trading_bot._get_ohlc(symbol, today, today, interval)
        # if not ohlc_data:
        #     print(f"❌ {symbol} OHLC 데이터 없음")
        #     continue

        close_price = ohlc_data[-1].close

        # 외인/기관 매매 추정치 조회
        response = trading_bot.get_investor_trend_estimate(symbol)
        # if not response:
        #     print(f"❌ {symbol} 추정 데이터 없음")
        #     continue

        summary = trading_bot.map_investor_estimates(response)
        # if not summary:
        #     print(f"❌ {symbol} 요약 데이터 없음")
        #     continue

        symbol_name = symbol_name_map.get(symbol, symbol)

        # 종목 헤더 메시지
        header = f"📈 ** {symbol_name} ({symbol})**\n📊 종가: {close_price:,}원"
        webhook.send_discord_webhook(header, "alarm")

        # 시간대별 매매 정보 모두 출력
        for row in summary:
            time_str = row["시간"]
            frgn_qty = row["외국인"]
            orgn_qty = row["기관"]
            sum_qty = row["총계"]

            frgn_amt = frgn_qty * close_price
            orgn_amt = orgn_qty * close_price
            sum_amt = sum_qty * close_price

            msg = (
                f"🕒 {time_str}\n"
                f"・🌏 외국인: {frgn_qty:+,}주 ({frgn_amt:+,.0f}원)\n"
                f"・🏦 기관: {orgn_qty:+,}주 ({orgn_amt:+,.0f}원)\n"
                f"・📦 총계: {sum_qty:+,}주 ({sum_amt:+,.0f}원)\n"
                f"---------------------------"
            )
            webhook.send_discord_webhook(msg, "alarm")

    return
    
def scheduled_save_account_balance():
    """
    스케줄러: 계좌 잔고 저장
    """
    
    trading_bot = AutoTradingBot(id=id, virtual=virtual)

    kst = timezone("Asia/Seoul")
    updated_at = int(datetime.now(kst).timestamp() * 1000)

    holdings = trading_bot.get_holdings_with_details()
    
    dynamodb_executor = DynamoDBExecutor()

    # ✅ 3. 기존 잔고 모두 삭제
    existing_items = AutoTradingBalance.query(trading_bot_name)
    for item in existing_items:
        try:
            item.delete()
            print(f'🗑️ 삭제된 종목: {item.symbol}')
        except Exception as e:
            print(f'❌ 삭제 실패 ({item.symbol}): {e}')

    # ✅ 4. 현재 잔고 다시 저장
    for holding in holdings:
        try:
            model = AutoTradingBalance(
                trading_bot_name=trading_bot_name,
                symbol=holding['symbol'],
                updated_at=updated_at,
                symbol_name=holding['symbol_name'],
                market=holding['market'],
                quantity=holding['quantity'],
                avg_price=holding['price'],
                amount=holding['amount'],
                profit=holding['profit'],
                profit_rate=holding['profit_rate'],
            )

            dynamodb_executor.execute_save(model)
            print(f'[💾 잔고 저장] {holding["symbol"]}')

        except Exception as e:
            print(f"❌ 잔고 저장 실패 ({holding['symbol_name']}): {e}")


def scheduled_single_buy_task():
    """
    테스트용: 특정 종목 1주 자동 매수 (시장가)
    """

    # ✅ 인스턴스 생성
    trading_bot = AutoTradingBot(id="schedulerbot", virtual=False)

    # ✅ 매수할 종목 정보 (원하는 종목으로 변경 가능)
    symbol = "300720"        # 삼성전자
    target_trade_value_krw = 10000000

    quote = trading_bot._get_quote(symbol=symbol)
    #qty = math.floor(target_trade_value_krw / quote.close) # 주식 매매 개수
    qty = 1
    buy_price = None         # 시장가 매수 (지정가 입력 시 가격 설정)
    sell_price = None
    symbol_name = '한일시멘트'
    
    print(f"[{datetime.now()}] 자동 매수 실행: 종목 {symbol}, 수량 {qty}주")

    try:
        trading_bot.place_order(
            symbol=symbol,
            qty=qty,
            symbol_name = symbol_name,
            sell_price=sell_price,   # 시장가 매수
            order_type="sell"
        )
    except Exception as e:
        print(f"❌ 매수 실패: {e}")
        
        