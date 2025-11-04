import datetime
import numpy as np
import pandas as pd
import requests
import math
import json
import os
import boto3

from pykis import PyKis, KisChart, KisStock, KisQuote, KisAccessToken, KisOrderableAmount
from datetime import datetime, date, time, timedelta
import mplfinance as mpf
from pytz import timezone
from app.utils.dynamodb.model.simulation_history_model import SimulationHistory
from app.utils.technical_indicator import TechnicalIndicator
from app.utils.webhook import Webhook
from app.utils.trading_logic import TradingLogic
from app.utils.crud_sql import SQLExecutor
from app.utils.dynamodb.crud import DynamoDBExecutor
from app.utils.database import get_db, get_db_session
from app.utils.dynamodb.model.trading_history_model import TradingHistory
from app.utils.dynamodb.model.auto_trading_model import AutoTrading
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol, StockSymbol2
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance
from app.utils.dynamodb.model.user_info_model import UserInfo
from pykis import KisBalance, KisOrderProfits
from decimal import Decimal


# 보조지표 클래스 선언
indicator = TechnicalIndicator()
logic = TradingLogic()
webhook = Webhook()

class AutoTradingBot:
    """
        실전투자와 모의투자를 선택적으로 설정 가능
    """
    def __init__(self, id, virtual=False, app_key=None, secret_key=None, account=None):

        result = list(UserInfo.scan(
            filter_condition=(UserInfo.id == id)
        ))

        if len(result) == 0:
            raise ValueError(f"사용자 {id}에 대한 정보를 찾을 수 없습니다.")

        self.kis_id = result[0].kis_id
        self.app_key = result[0].app_key
        self.secret_key = result[0].secret_key
        self.account = result[0].account
        self.virtual = virtual
        self.virtual_kis_id = result[0].virtual_kis_id
        self.virtual_app_key = result[0].virtual_app_key
        self.virtual_secret_key = result[0].virtual_secret_key
        self.virtual_account = result[0].virtual_account

        # 임의로 app_key 및 secret_key 넣고 싶을 경우
        if app_key and secret_key and account:
            if virtual:
                self.virual_app_key = app_key
                self.virual_secret_key = secret_key
                self.virual_account = account
            else:
                self.app_key = app_key
                self.secret_key = secret_key
                self.account = account

        # PyKis 객체 생성
        self.create_kis_object()    

    def create_kis_object(self):
        """한 번 발급받은 토큰을 유지하면서 PyKis 객체 생성"""
        # 모의투자용 PyKis 객체 생성
        if self.virtual:
            if not all([self.kis_id, self.app_key, self.secret_key, 
                        self.virtual_kis_id, self.virtual_app_key, self.virtual_secret_key, self.virtual_account]):
                raise ValueError("모의투자 정보를 완전히 제공해야 합니다.")
            
            self.kis = PyKis(
                id=self.kis_id,         # 한국투자증권 HTS ID
                appkey=self.app_key,    # 발급받은 App Key
                secretkey=self.secret_key, # 발급받은 App Secret
                account=self.virtual_account, # 계좌번호 (예: "12345678-01")
                virtual_id=self.virtual_kis_id,
                virtual_appkey=self.virtual_app_key,
                virtual_secretkey=self.virtual_secret_key,
                keep_token=True  # API 접속 토큰 자동 저장
            )
        # 실전투자용 PyKis 객체 생성
        else:
            self._get_token()  # 토큰을 S3에서 가져오거나 생성
            self.kis = PyKis(
                id=self.kis_id,             # 한국투자증권 HTS ID
                appkey=self.app_key,    # 발급받은 App Key
                secretkey=self.secret_key, # 발급받은 App Secret
                account=self.account, # 계좌번호 (예: "12345678-01")
                token=KisAccessToken.load("token.json"),  # 토큰 파일에서 로드
                keep_token=True           # 토큰 자동 갱신 여부
            )
            self._save_token()  # 토큰을 S3에 저장

        print(f"{'모의투자' if self.virtual else '실전투자'} API 객체가 성공적으로 생성되었습니다.")

    def _get_token(self):     
        s3_client = boto3.client('s3', region_name='ap-northeast-2', endpoint_url='https://s3.ap-northeast-2.amazonaws.com', config=boto3.session.Config(signature_version='s3v4'))
        bucket_name="sb-fsts"

        token_save_path = f"credentials/pykis/token.json"

        response = s3_client.get_object(Bucket=bucket_name, Key=token_save_path)

        # 본문 읽기 및 JSON 파싱
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)
        with open("token.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def _save_token(self):
        s3_client = boto3.client('s3', region_name='ap-northeast-2', endpoint_url='https://s3.ap-northeast-2.amazonaws.com', config=boto3.session.Config(signature_version='s3v4'))
        bucket_name="sb-fsts"

        token_save_path = f"credentials/pykis/token.json"

        s3_client.upload_file(
            Filename="token.json",
            Bucket=bucket_name,
            Key=token_save_path
        )

    # 봉 데이터를 가져오는 함수
    def _get_ohlc(self, symbol, start_date, end_date, interval='day', mode="default"):
        symbol_stock: KisStock = self.kis.stock(symbol)  # SK하이닉스 (코스피)
        chart: KisChart = symbol_stock.chart(
            start=start_date,
            end=end_date,
            period=interval
        ) # 2023년 1월 1일부터 2023년 12월 31일까지의 일봉입니다.
        klines = chart.bars

        # 첫 번째 데이터를 제외하고, 각 항목의 open 값을 전날 close 값으로 변경 
        # mode = continuous
        if mode == 'continuous':
            for i in range(1, len(klines)):
                klines[i].open = klines[i - 1].close  # 전날의 close로 open 값을 변경
            
        return klines

    def calculate_pnl(self, trading_history, current_price, trade_amount):
        """Parameters:
        - trading_history: dict, 거래 내역 및 계산 결과 저장
        - current_price: float, 현재 가격
        -initial_capital: 초기 자본
        """
        
        total_cost = 0  # 총 비용
        total_quantity = 0  # 총 수량
        total_realized_pnl = 0  # 실현 손익
        buy_count = 0  # 총 매수 횟수
        sell_count = 0  # 총 매도 횟수
        buy_dates = []  # 매수 날짜 목록
        sell_dates = []  # 매도 날짜 목록
        investment_cost = 0
        
        # 포지션별 계산
        for trade in trading_history['history']:
            
            if trade['position'] == 'BUY':  # 매수일 경우
                # 매수수의 실현 손익 계산
                buy_quantity = trade['quantity']
                buy_price = trade['price']
                                
                total_cost += buy_price * buy_quantity  # 비용 증가
                investment_cost += buy_price * buy_quantity
                total_quantity += buy_quantity  # 수량 증가
                buy_count += 1  # 매수 횟수 증가
                buy_dates.append(trade['time'])  # 매수 날짜 추가
                
            elif trade['position'] == 'SELL':  # 매도일 경우
                if total_quantity <= 0:
                    raise ValueError("포지션 수량이 없습니다!")
                    
                # 매도의 실현 손익 계산
                sell_quantity = trade['quantity']
                sell_price = trade['price']
                
                # 평균가 계산
                average_price = total_cost / total_quantity if total_quantity > 0 else 0
                
                #평균가로 매도 손익 계산
                total_realized_pnl += (sell_price - average_price) * sell_quantity
                
                # 매도 후 수량 및 비용 감소
                total_quantity -= sell_quantity
                total_cost -= average_price * sell_quantity
                #비용이 음수가 되지 않도록 처리
                total_cost = max(total_cost, 0)
                
                sell_count += 1  # 매도 횟수 증가
                sell_dates.append(trade['time'])  # 매도 날짜 추가
            
            # 모든 주식을 매도했을 경우 비용 리셋
            if total_quantity == 0:
                total_cost = 0
                
        # 평균 단가 계산(잔여 수량이 있는 경우)
        average_price = total_cost / total_quantity if total_quantity > 0 else 0

        # 미실현 손익 계산
        unrealized_pnl = (current_price - average_price) * total_quantity if total_quantity > 0 else 0
        realized_roi = (total_realized_pnl/trade_amount)*100 if trade_amount > 0 else 0
        unrealized_roi = ((total_realized_pnl + unrealized_pnl)/trade_amount)*100 if trade_amount > 0 else 0

        # 결과 저장
        trading_history.update({
            'average_price': average_price,  # 평균 매수 가격
            'realized_pnl': total_realized_pnl,  # 실현 손익
            'unrealized_pnl': unrealized_pnl,  # 미실현 손익
            'realized_roi' : realized_roi,
            'unrealized_roi' : unrealized_roi,
            'total_cost': total_cost,  # 총 매수 비용
            'total_quantity': total_quantity,  # 총 보유 수량
            'buy_count': buy_count,  # 매수 횟수
            'sell_count': sell_count,  # 매도 횟수
            'buy_dates': buy_dates,  # 매수 날짜 목록
            'sell_dates': sell_dates,  # 매도 날짜 목록
        })
        print(f"매수금액: {trade_amount}")
        print(f"투자비용: {investment_cost}")
        return trading_history
    

    def simulate_trading(
            self, symbol, stock_name, stock_type, start_date, end_date, target_trade_value_krw, target_trade_value_ratio, min_trade_value, buy_trading_logic=None, sell_trading_logic=None,
            interval='day', buy_percentage = None, ohlc_mode = 'default', initial_capital=None, rsi_period = 25, take_profit_logic=None, 
            stop_loss_logic=None, indicators=None
        ):

        valid_symbols = []
        
        # 지표 계산을 위해 180일 이전부터 OHLC 데이터를 가져옵니다.        
        start_date_for_ohlc = start_date - timedelta(days=300)

        valid_symbol = {}
        # ✅ OHLC 데이터 가져오기
        ohlc_data = self._get_ohlc(symbol, start_date_for_ohlc, end_date, interval, ohlc_mode)
        
        df = self._create_ohlc_df(ohlc_data=ohlc_data, symbol = symbol, start_date=start_date_for_ohlc, end_date=end_date, indicators=indicators, rsi_period=rsi_period)

        print(f" df2: {df}" )
        
        valid_symbol['symbol'] = symbol
        valid_symbol['stock_name'] = stock_name
        valid_symbol['stock_type'] = stock_type
        valid_symbol['ohlc_data'] = ohlc_data
        valid_symbol['df'] = df

        valid_symbols.append(valid_symbol)

        if not ohlc_data:
            print(f"❌ No OHLC data: {symbol}")
            return None, None, None
        
        # 익절, 손절 로직 별 다양화
        if take_profit_logic['name'] is None:
            use_take_profit = False
            take_profit_logic_name = None
            take_profit_ratio = 0
        else:
            use_take_profit = True
            take_profit_logic_name = take_profit_logic['name']
            take_profit_ratio = take_profit_logic['params']['ratio']

        if stop_loss_logic['name'] is None:
            use_stop_loss = False
            stop_loss_logic_name = None
            stop_loss_ratio = 0
        else:
            use_stop_loss = True
            stop_loss_logic_name = stop_loss_logic['name']
            stop_loss_ratio = stop_loss_logic['params']['ratio']

        symbols = valid_symbols   
        trade_ratio = target_trade_value_ratio  # None 이면 직접 입력 방식

        account_holdings = []
        simulation_histories = []

        # account
        global_state = {
            'initial_capital': initial_capital,
            'krw_balance': initial_capital,
            'account_holdings': account_holdings
        }

        # 공통된 모든 날짜 모으기
        all_dates = set()
        dates = [pd.Timestamp(c.time).tz_localize(None).normalize() for c in ohlc_data]
        all_dates.update(d for d in dates if d >= start_date)

        holding = {
            'symbol': symbol,
            'stock_name': stock_name,
            'stock_type': stock_type,
            'timestamp_str': "",
            'close_price': 0,
            'total_quantity': 0,
            'avg_price': 0,
            'total_buy_cost': 0,
            'take_profit_logic': {
                'name': take_profit_logic_name,
                'ratio': take_profit_ratio,
                'max_close_price': 0  # trailing stop loss를 위한 최고가
            },
            'stop_loss_logic': {
                'name': stop_loss_logic_name,
                'ratio': stop_loss_ratio,
                'max_close_price': 0  # trailing stop loss를 위한 최고가
            },
            'trading_histories': []
        }

        global_state['account_holdings'].append(holding)

        date_range = sorted(list(all_dates))  # 날짜 정렬

        # ✅ 시뮬레이션 시작
        for idx, current_date in enumerate(date_range): # ✅ 하루 기준 고정 portfolio_value 계산 (종목별 보유 상태 반영)
            for holding in global_state['account_holdings']:
                symbol = holding['symbol']

                # symbols 리스트에서 해당 symbol과 일치하는 s 찾기
                s = next((s for s in symbols if s['symbol'] == symbol), None)

                if s is None:
                    print(f"❌ 해당 symbol 종목이 없습니다: {symbol}")
                    continue  # 해당 symbol 종목이 없으면 건너뜀

                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]

                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next = lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next = lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                sell_yn = False
                buy_yn = False
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price

                # ✅ 익절/손절 조건 우선 적용
                if holding['total_quantity'] > 0:
                    current_roi = ((close_price - holding['avg_price']) / holding['avg_price']) * 100

                    # 익절 조건 계산
                    if take_profit_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif take_profit_logic_name == 'trailing': # 종가 최고점 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100
                    else:
                        target_roi = current_roi

                    # 익절 조건
                    if use_take_profit and target_roi >= take_profit_ratio:
                        # 실제 매도 조건 충족
                        fee = holding['total_quantity'] * close_price * 0.00014
                        tax = holding['total_quantity'] * close_price * 0.0015
                        revenue = holding['total_quantity'] * close_price - fee - tax
                        realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        global_state['krw_balance'] += revenue

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        take_profit_hit = True
                        reason = f"익절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=holding['stock_name'],
                            stock_type = holding['stock_type'],
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        sell_yn = True

                        simulation_histories.append(trading_history)

                    # 손절 조건 계산
                    if stop_loss_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif stop_loss_logic_name == 'trailing': # 최고가 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100 
                    else:
                        target_roi = current_roi

                    # 손절 조건
                    if use_stop_loss and target_roi <= -stop_loss_ratio:
                        # 실제 손절 조건 충족
                        fee = holding['total_quantity'] * close_price * 0.00014
                        tax = holding['total_quantity'] * close_price * 0.0015
                        revenue = holding['total_quantity'] * close_price - fee - tax
                        realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        global_state['krw_balance'] += revenue

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        stop_loss_hit = True
                        reason = f"손절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=holding['stock_name'],
                            stock_type = holding['stock_type'],
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        sell_yn = True

                        simulation_histories.append(trading_history)

                # ✅ 매도 조건 (익절/손절 먼저 처리됨, 이 블럭은 전략 로직 기반 매도)
                sell_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=sell_trading_logic,
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='SELL',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 매도 실행
                if len(sell_logic_reasons) > 0 and holding['total_quantity'] > 0:
                    fee = holding['total_quantity'] * close_price * 0.00014
                    tax = holding['total_quantity'] * close_price * 0.0015
                    revenue = holding['total_quantity'] * close_price - fee - tax
                    realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                    realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                    unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                    unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                    global_state['krw_balance'] += revenue

                    trade_quantity = holding['total_quantity']

                    holding['total_quantity'] = 0
                    holding['total_buy_cost'] = 0
                    holding['avg_price'] = 0
                    holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                    reason = ""

                    trading_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=holding['stock_name'],
                        stock_type = holding['stock_type'],
                        fee=fee,
                        tax=tax,
                        revenue=revenue,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason=reason,
                        trade_type='SELL',
                        trade_quantity=trade_quantity,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=realized_pnl,
                        realized_roi=realized_roi,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    holding['trading_histories'].append(trading_history)

                    sell_yn = True

                    simulation_histories.append(trading_history)
            
            # 매수 로직만 확인
            for s in symbols:
                symbol = s['symbol']
                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']

                # 알맞은 종목 찾기
                holding = next((h for h in global_state['account_holdings'] if h['symbol'] == symbol), None)

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]

                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next = lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next = lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                sell_yn = False
                buy_yn = False
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price
                
                # ✅ 매수 조건
                buy_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=buy_trading_logic,
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='BUY',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 직접 지정된 target_trade_value_krw가 있으면 사용, 없으면 비율로 계산
                if target_trade_value_krw and target_trade_value_krw > 0:
                    trade_amount = min(target_trade_value_krw, global_state['krw_balance'])
                    min_trade_value = 0 # 고정 금액의 경우 min_trade_value는 무시
                else:
                    trade_ratio = trade_ratio if trade_ratio is not None else 100
                    
                    # 현재 총 자산을 구하기 위한 로직 
                    # 평가액
                    total_market_value = 0
                    for h in global_state['account_holdings']:
                        market_value = h['avg_price'] * h['total_quantity']
                        total_market_value += market_value

                    total_balance = global_state['krw_balance'] + total_market_value
                    trade_amount = min(total_balance * (trade_ratio / 100), global_state['krw_balance'])

                # 매수 제약 조건 체크
                if buy_percentage is None:
                    buy_condition = True
                else:
                    # 매수 비율이 지정되어 있을 경우, 현재 종가와 평균가의 차이가 매수 비율보다 클 때만 매수
                    if holding['avg_price'] == 0:
                        buy_condition = True
                    else:
                        if buy_percentage < abs(holding['avg_price'] - close_price) / holding['avg_price'] * 100:
                            buy_condition = True
                        else:
                            buy_condition = False
                # ✅ 매수 실행
                if len(buy_logic_reasons) > 0 and min_trade_value <= trade_amount and buy_condition: # 최소 금액 이상일 때, buy_percentage 보다 클 때만 매수
                    buy_quantity = math.floor(trade_amount / close_price)
                    cost = buy_quantity * close_price
                    fee = cost * 0.00014
                    tax = 0
                    total_buy_cost = cost + fee
                    
                    # 매수 금액이 예수금보다 작거나 같을 때만 매수
                    if buy_quantity > 0 and total_buy_cost <= global_state['krw_balance']:

                        global_state['krw_balance'] -= total_buy_cost
                        holding['total_buy_cost'] += total_buy_cost
                        holding['total_quantity'] += buy_quantity
                        holding['avg_price'] = holding['total_buy_cost'] / holding['total_quantity']
                        
                        if holding['stop_loss_logic']['max_close_price'] < close_price:
                            holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트

                        revenue = 0
                        realized_pnl = 0
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        trade_quantity = buy_quantity

                        reason = ""

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=holding['stock_name'],
                            stock_type = holding['stock_type'],
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='BUY',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        buy_yn = True

                        simulation_histories.append(trading_history)
                
                # holding['trading_histories'] 를 활용해서 이미 매매가 이루어진 경우를 확인
                already_traded_yn = any(
                    history['timestamp_str'] == timestamp_str and history['trade_type'] in ('BUY', 'SELL')
                    for history in holding['trading_histories']
                )

                # 매매가 이루어지지 않은 경우
                if already_traded_yn is False:

                    unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                    unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                    # 최고가 trailing 하고 있을 경우
                    if holding['stop_loss_logic']['max_close_price'] > 0 and holding['stop_loss_logic']['max_close_price'] < close_price:
                        holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트

                    simulation_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=stock_name,
                        stock_type = stock_type,
                        fee=0,
                        tax=0,
                        revenue=0,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason="",
                        trade_type=None,
                        trade_quantity=0,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=0,
                        realized_roi=0,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    simulation_histories.append(simulation_history)
                
        # start_date 이후 필터링
        filtered_df = df[df.index >= pd.Timestamp(start_date)]

        filtered_df['Buy_Signal'] = np.nan
        filtered_df['Sell_Signal'] = np.nan
        
        return filtered_df, global_state, simulation_histories


    def _convert_float(self, value):
        if value is None:
            return 0.0  # 또는 return np.nan
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0  # 또는 np.nan
    
    def simulate_trading_bulk(self, simulation_settings):

        buy_percentage = simulation_settings.get("buy_percentage", None)

        valid_symbols = []

        start_date = simulation_settings["start_date"] - timedelta(days=180)
        end_date = simulation_settings["end_date"]
        interval = simulation_settings["interval"]

        failed_stocks = set()  # 중복 제거 자동 처리
        
        # 사전에 계산된 OHLC 데이터와 DataFrame을 저장 (api 이슈)
        for stock_name, symbol in simulation_settings["selected_symbols"].items():
            
            valid_symbol = {}
            try:
                # ✅ OHLC 데이터 가져오기
                ohlc_data = self._get_ohlc(symbol, start_date, end_date, interval)
                rsi_period = simulation_settings['rsi_period']
                
                df = self._create_ohlc_df(ohlc_data=ohlc_data, symbol = symbol, start_date=start_date, end_date=end_date, rsi_period=rsi_period)
                
                        # ✅ type 가져오기
                stock_type_map = simulation_settings['stock_type']
                stock_type = stock_type_map.get(symbol, "unknown")
        
                # 유효한 종목만 저장
                valid_symbol['symbol'] = symbol
                valid_symbol['stock_name'] = stock_name
                valid_symbol['ohlc_data'] = ohlc_data
                valid_symbol['df'] = df
                valid_symbol['stock_type'] = stock_type

                valid_symbols.append(valid_symbol)

            except Exception as e:
                # 지표 계산에 실패한 종목 리스트
                print(f'{stock_name} 지표 계산 실패. 사유 : {str(e)}')
                failed_stocks.add(stock_name)
                        
        # ✅ 세션 상태에 저장
        simulation_settings["selected_symbols"] = valid_symbols #simulation_settings["selected_symbols"]에 type 추가되도 괜찮?

        symbols = valid_symbols
        trade_ratio = simulation_settings.get("target_trade_value_ratio", 100)
        target_trade_value_krw = simulation_settings.get("target_trade_value_krw")
        min_trade_value = simulation_settings.get("min_trade_value", 0)

        account_holdings = []
        simulation_histories = []

        # account
        global_state = {
            'initial_capital': simulation_settings["initial_capital"],
            'krw_balance': simulation_settings["initial_capital"],
            'account_holdings': account_holdings
        }
        
        # 익절, 손절 로직 별 다양화
        if simulation_settings['take_profit_logic']['name'] is None:
            use_take_profit = False
            take_profit_ratio = 0
        else:
            use_take_profit = True
            take_profit_logic_name = simulation_settings['take_profit_logic']['name']
            take_profit_ratio = simulation_settings['take_profit_logic']['params']['ratio']

        if simulation_settings['stop_loss_logic']['name'] is None:
            use_stop_loss = False
            stop_loss_ratio = 0
        else:
            use_stop_loss = True
            stop_loss_logic_name = simulation_settings['stop_loss_logic']['name']
            stop_loss_ratio = simulation_settings['stop_loss_logic']['params']['ratio']

        start_date = pd.Timestamp(simulation_settings["start_date"]).normalize()
        # 공통된 모든 날짜 모으기
        all_dates = set()
        for symbol in symbols:
            ohlc_data = symbol['ohlc_data']
            dates = [pd.Timestamp(c.time).tz_localize(None).normalize() for c in ohlc_data]
            all_dates.update(d for d in dates if d >= start_date)

            holding_dict = {
                'symbol': symbol['symbol'],
                'stock_name': stock_name,
                'stock_type': stock_type,
                'timestamp_str': "",
                'close_price': 0,
                'total_quantity': 0,
                'avg_price': 0,
                'total_buy_cost': 0,
                'take_profit_logic': {
                    'name': take_profit_logic_name,
                    'ratio': take_profit_ratio,
                    'max_close_price': 0  # trailing stop loss를 위한 최고가
                },
                'stop_loss_logic': {
                    'name': stop_loss_logic_name,
                    'ratio': stop_loss_ratio,
                    'max_close_price': 0  # trailing stop loss를 위한 최고가
                },
                'trading_histories': []
            }

            global_state['account_holdings'].append(holding_dict)
            


        date_range = sorted(list(all_dates))  # 날짜 정렬

        # total count 반영
        dynamodb_executor = DynamoDBExecutor()

        pk_name = 'simulation_id'

        # 한국 시간대
        kst = timezone("Asia/Seoul")
        # 현재 시간을 KST로 변환
        current_time = datetime.now(kst)
        updated_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성
        updated_at_dt = current_time.strftime("%Y-%m-%d %H:%M:%S")
        completed_task_cnt = 0

        data_model = SimulationHistory(
            simulation_id=simulation_settings['simulation_id'],
            updated_at=updated_at,
            updated_at_dt=updated_at_dt,
            total_task_cnt=len(date_range)
        )

        result = dynamodb_executor.execute_update(data_model, pk_name)
   
        # ✅ 시뮬레이션 시작
        for idx, current_date in enumerate(date_range): # ✅ 하루 기준 고정 portfolio_value 계산 (종목별 보유 상태 반영)            
            for holding in global_state['account_holdings']:
                symbol = holding['symbol']

                # symbols 리스트에서 해당 symbol과 일치하는 s 찾기
                s = next((s for s in symbols if s['symbol'] == symbol), None)

                if s is None:
                    print(f"❌ 해당 symbol 종목이 없습니다: {symbol}")
                    continue  # 해당 symbol 종목이 없으면 건너뜀

                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']
                stock_type = s['stock_type']

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]
    
                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next=lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next=lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                sell_yn = False
                buy_yn = False
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price

                # ✅ 익절/손절 조건 우선 적용
                if holding['total_quantity'] > 0:
                    current_roi = ((close_price - holding['avg_price']) / holding['avg_price']) * 100

                    # 익절 조건 계산
                    if take_profit_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif take_profit_logic_name == 'trailing': # 종가 최고점 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100
                    else:
                        target_roi = current_roi

                    # 익절 조건
                    if use_take_profit and target_roi >= take_profit_ratio:
                        # 실제 매도 조건 충족
                        fee = holding['total_quantity'] * close_price * 0.00014
                        tax = holding['total_quantity'] * close_price * 0.0015
                        revenue = holding['total_quantity'] * close_price - fee - tax
                        realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        global_state['krw_balance'] += revenue

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        take_profit_hit = True
                        reason = f"익절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type = stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        sell_yn = True

                        simulation_histories.append(trading_history)

                    # 손절 조건 계산
                    if stop_loss_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif stop_loss_logic_name == 'trailing': # 최고가 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100 
                    else:
                        target_roi = current_roi

                    # 손절 조건
                    if use_stop_loss and target_roi <= -stop_loss_ratio:
                        # 실제 손절 조건 충족
                        fee = holding['total_quantity'] * close_price * 0.00014
                        tax = holding['total_quantity'] * close_price * 0.0015
                        revenue = holding['total_quantity'] * close_price - fee - tax
                        realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        global_state['krw_balance'] += revenue

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        stop_loss_hit = True
                        reason = f"손절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type = stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        sell_yn = True

                        simulation_histories.append(trading_history)

                # ✅ 매도 조건 (익절/손절 먼저 처리됨, 이 블럭은 전략 로직 기반 매도)
                sell_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=simulation_settings["sell_trading_logic"],
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='SELL',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 매도 실행
                if len(sell_logic_reasons) > 0 and holding['total_quantity'] > 0:
                    fee = holding['total_quantity'] * close_price * 0.00014
                    tax = holding['total_quantity'] * close_price * 0.0015
                    revenue = holding['total_quantity'] * close_price - fee - tax
                    realized_pnl = revenue - (holding['avg_price'] * holding['total_quantity'])
                    realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                    unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                    unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                    global_state['krw_balance'] += revenue

                    trade_quantity = holding['total_quantity']

                    holding['total_quantity'] = 0
                    holding['total_buy_cost'] = 0
                    holding['avg_price'] = 0
                    holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                    reason = ""

                    trading_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=stock_name,
                        stock_type = stock_type,
                        fee=fee,
                        tax=tax,
                        revenue=revenue,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason=reason,
                        trade_type='SELL',
                        trade_quantity=trade_quantity,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=realized_pnl,
                        realized_roi=realized_roi,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    holding['trading_histories'].append(trading_history)

                    sell_yn = True

                    simulation_histories.append(trading_history)

            # 매수 로직만 확인                    
            for s in symbols:
                symbol = s['symbol']
                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']
                stock_type = s['stock_type']
                
                # 알맞은 종목 찾기
                holding = next((h for h in global_state['account_holdings'] if h['symbol'] == symbol), None)

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]
    
                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next=lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next=lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                sell_yn = False
                buy_yn = False
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price
  
                # ✅ 매수 조건
                buy_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=simulation_settings["buy_trading_logic"],
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='BUY',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 직접 지정된 target_trade_value_krw가 있으면 사용, 없으면 비율로 계산
                if target_trade_value_krw and target_trade_value_krw > 0:
                    trade_amount = min(target_trade_value_krw, global_state['krw_balance'])
                    min_trade_value = 0 # 고정 금액의 경우 min_trade_value는 무시
                else:
                    trade_ratio = trade_ratio if trade_ratio is not None else 100
                    
                    # 현재 총 자산을 구하기 위한 로직 
                    total_market_value = 0
                    for h in global_state['account_holdings']:
                        market_value = h['avg_price'] * h['total_quantity']
                        total_market_value += market_value

                    total_balance = global_state['krw_balance'] + total_market_value
                    trade_amount = min(total_balance * (trade_ratio / 100), global_state['krw_balance'])

                # 매수 제약 조건 체크
                if buy_percentage is None:
                    buy_condition = True
                else:
                    # 매수 비율이 지정되어 있을 경우, 현재 종가와 평균가의 차이가 매수 비율보다 클 때만 매수
                    if holding['avg_price'] == 0:
                        buy_condition = True
                    else:
                        if buy_percentage < abs(holding['avg_price'] - close_price) / holding['avg_price'] * 100:
                            buy_condition = True
                        else:
                            buy_condition = False

                # ✅ 매수 실행
                if len(buy_logic_reasons) > 0 and min_trade_value <= trade_amount and buy_condition: # 최소 금액 이상일 때, buy_percentage 보다 클 때만 매수
                    buy_quantity = math.floor(trade_amount / close_price)
                    cost = buy_quantity * close_price
                    fee = cost * 0.00014
                    tax = 0
                    total_buy_cost = cost + fee
                    
                    # 매수 금액이 예수금보다 작거나 같을 때만 매수
                    if buy_quantity > 0 and total_buy_cost <= global_state['krw_balance']:

                        global_state['krw_balance'] -= total_buy_cost
                        holding['total_buy_cost'] += total_buy_cost
                        holding['total_quantity'] += buy_quantity
                        holding['avg_price'] = holding['total_buy_cost'] / holding['total_quantity']

                        if holding['stop_loss_logic']['max_close_price'] < close_price:
                            holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트

                        revenue = 0
                        realized_pnl = 0
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        trade_quantity = buy_quantity

                        reason = ""

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type = stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='BUY',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        buy_yn = True

                        simulation_histories.append(trading_history)
                
                # holding['trading_histories'] 를 활용해서 이미 매매가 이루어진 경우를 확인
                already_traded_yn = any(
                    history['timestamp_str'] == timestamp_str and history['trade_type'] in ('BUY', 'SELL')
                    for history in holding['trading_histories']
                )

                # 매매가 이루어지지 않은 경우
                if already_traded_yn is False:

                    unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                    unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                    # 최고가 trailing 하고 있을 경우
                    if holding['stop_loss_logic']['max_close_price'] > 0 and holding['stop_loss_logic']['max_close_price'] < close_price:
                        holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트
                        
                    # 아무런 매수 없이 히스토리만 생성
                    simulation_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=stock_name,
                        stock_type = stock_type,
                        fee=0,
                        tax=0,
                        revenue=0,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason="",
                        trade_type=None,
                        trade_quantity=0,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=0,
                        realized_roi=0,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    simulation_histories.append(simulation_history)
        
            # completed_task_cnt 반영
            completed_task_cnt = completed_task_cnt + 1
            data_model = SimulationHistory(
                simulation_id=simulation_settings['simulation_id'],
                updated_at=updated_at,
                updated_at_dt=updated_at_dt,
                completed_task_cnt=completed_task_cnt
            )

            result = dynamodb_executor.execute_update(data_model, pk_name)
    
        return global_state, simulation_histories, failed_stocks


    def _create_trading_history(
        self, symbol, stock_name, stock_type, fee, tax, revenue, timestamp, timestamp_str, reason, trade_type, trade_quantity,
        avg_price, buy_logic_reasons, sell_logic_reasons, take_profit_hit, stop_loss_hit,
        realized_pnl, realized_roi, unrealized_pnl, unrealized_roi, krw_balance, total_quantity, total_buy_cost, close_price
    ):

        trading_history = {}

        trading_history['symbol'] = symbol
        trading_history['stock_name'] = stock_name
        trading_history['stock_type'] = stock_type
        trading_history['fee'] = fee
        trading_history['tax'] = tax
        trading_history['revenue'] = revenue
        trading_history['timestamp'] = timestamp
        trading_history['timestamp_str'] = timestamp_str
        trading_history['reason'] = reason
        trading_history['trade_type'] = trade_type
        trading_history['trade_quantity'] = trade_quantity
        trading_history['avg_price'] = avg_price
        trading_history['buy_logic_reasons'] = buy_logic_reasons
        trading_history['sell_logic_reasons'] = sell_logic_reasons
        trading_history['take_profit_hit'] = take_profit_hit
        trading_history['stop_loss_hit'] = stop_loss_hit
        trading_history['realized_pnl'] = realized_pnl
        trading_history['realized_roi'] = realized_roi
        trading_history['unrealized_pnl'] = unrealized_pnl
        trading_history['unrealized_roi'] = unrealized_roi
        trading_history['krw_balance'] = krw_balance
        trading_history['total_quantity'] = total_quantity
        trading_history['total_buy_cost'] = total_buy_cost
        trading_history['close_price'] = close_price

        return trading_history


    def _create_ohlc_df(self, ohlc_data, symbol, start_date, end_date,  indicators=[], rsi_period=25):

        # ✅ OHLC → DataFrame 변환
        timestamps = [c.time for c in ohlc_data]
        ohlc = [
            [c.time, float(c.open), float(c.high), float(c.low), float(c.close), float(c.volume)]
            for c in ohlc_data
        ]
        df = pd.DataFrame(ohlc, columns=["Time", "Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex(timestamps))
        df.index = df.index.tz_localize(None)

        # ✅ 공매도 데이터 병합
        if symbol and start_date and end_date:
            try:

                short_df = self.get_short_sale_daily_trend_df_multi(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                )

                if short_df is not None and not short_df.empty:
                    short_df.index = pd.to_datetime(short_df.index).tz_localize(None)

                    # ✅ 병합: index 기준으로만 병합, '영업일자' 컬럼 제거
                    df = df.merge(short_df, how="left", left_index=True, right_index=True)
                    df.drop(columns=[col for col in df.columns if col == "영업일자"], inplace=True, errors="ignore")

            except Exception as e:
                print(f"⚠️ 공매도 데이터 병합 실패: {e}")
                
        indicator = TechnicalIndicator()
        
        lookback_prev = 5
        lookback_next = 5

        # 차트에 그리기 위한 지표 계산
        for i in indicators:
            if i['type'] == 'ema' and i['draw_yn'] is True:
                df = indicator.cal_ema_df(df, i['period'])
            elif i['type'] == 'sma' and i['draw_yn'] is True:
                df = indicator.cal_sma_df(df, i['period'])

        # 지표 계산
        df = indicator.cal_ema_df(df, 5)
        df = indicator.cal_ema_df(df, 10)
        df = indicator.cal_ema_df(df, 13)
        df = indicator.cal_ema_df(df, 20)
        df = indicator.cal_ema_df(df, 21)
        df = indicator.cal_ema_df(df, 55)
        df = indicator.cal_ema_df(df, 60)
        df = indicator.cal_ema_df(df, 89)
        df = indicator.cal_ema_df(df, 120)
        df = indicator.cal_ema_df(df, 200)
        
        df = indicator.cal_sma_df(df, 5)
        df = indicator.cal_sma_df(df, 10)
        df = indicator.cal_sma_df(df, 20)
        df = indicator.cal_sma_df(df, 40)
        df = indicator.cal_sma_df(df, 60)
        df = indicator.cal_sma_df(df, 120)
        df = indicator.cal_sma_df(df, 200)

        df = indicator.cal_rsi_df(df, rsi_period)
        df = indicator.cal_macd_df(df)
        df = indicator.cal_stochastic_df(df)
        df = indicator.cal_mfi_df(df)
        df = indicator.cal_bollinger_band(df)
        df = indicator.cal_horizontal_levels_df(df, lookback_prev, lookback_next)
        
        df = indicator.cal_wma_df(df, 5)
        df = indicator.cal_wma_df(df, 10)
        df = indicator.cal_wma_df(df, 20)
        df = indicator.cal_wma_df(df, 60)
        df = indicator.cal_wma_df(df, 120)
        df = indicator.cal_wma_df(df, 200)        
                                
        # 🔧 EMA 기울기 추가 및 이동평균 계산
        #df['EMA_55_Slope'] = df['EMA_55'] - df['EMA_55'].shift(1)
        df['EMA_89_Slope'] = df['EMA_89'] - df['EMA_89'].shift(1)
        df['EMA_55_Slope'] = (df['EMA_55'] - df['EMA_55'].shift(1)) / df['EMA_55'].shift(1) * 100
        
        df['EMA_55_Slope_MA'] = df['EMA_55_Slope'].rolling(window=3).mean()
        df['EMA_89_Slope_MA'] = df['EMA_89_Slope'].rolling(window=3).mean()
        
        return df
    

    # 실시간 매매 함수
    def trade(self, trading_bot_name, buy_trading_logic, sell_trading_logic, selected_symbols, start_date, end_date, target_trade_value_krw, target_trade_value_ratio, min_trade_value, interval='day', max_allocation = 0.01, rsi_period=25, take_profit_logic=None, stop_loss_logic=None):
        
        valid_symbols = []

        start_date_for_ohlc = start_date - timedelta(days=180)  # OHLC 데이터는 180일 이전부터 가져옴
        
        failed_stocks = set()  # 중복 제거 자동 처리

        # 사전에 계산된 OHLC 데이터와 DataFrame을 저장 (api 이슈)
        for s in selected_symbols:
            
            # dynamodb 에서 가져오느라 그럼
            symbol = s.symbol
            stock_name = s.symbol_name
            stock_type = s.type

            valid_symbol = {}
            try:
                # ✅ OHLC 데이터 가져오기
                ohlc_data = self._get_ohlc(symbol, start_date_for_ohlc, end_date, interval)

                df = self._create_ohlc_df(ohlc_data=ohlc_data, symbol=symbol, start_date=start_date_for_ohlc, end_date=end_date, rsi_period=rsi_period)
                
                # 유효한 종목만 저장
                valid_symbol['symbol'] = symbol
                valid_symbol['stock_name'] = stock_name
                valid_symbol['stock_type'] = stock_type
                valid_symbol['ohlc_data'] = ohlc_data
                valid_symbol['df'] = df

                valid_symbols.append(valid_symbol)

            except Exception as e:
                # 지표 계산에 실패한 종목 리스트
                print(f'{stock_name} 지표 계산 실패. 사유 : {str(e)}')
                failed_stocks.add(stock_name)

        symbols = valid_symbols
        trade_ratio = target_trade_value_ratio
        target_trade_value_krw = target_trade_value_krw

        account_holdings = []
        simulation_histories = []

        # account
        global_state = {
            'initial_capital': 0,
            'krw_balance': 0,
            'account_holdings': account_holdings
        }

        # 익절, 손절 로직 별 다양화
        if take_profit_logic['name'] is None:
            use_take_profit = False
            take_profit_logic_name = None
            take_profit_ratio = 0
        else:
            use_take_profit = True
            take_profit_logic_name = take_profit_logic['name']
            take_profit_ratio = take_profit_logic['params']['ratio']

        if stop_loss_logic['name'] is None:
            use_stop_loss = False
            stop_loss_logic_name = None
            stop_loss_ratio = 0
        else:
            use_stop_loss = True
            stop_loss_logic_name = stop_loss_logic['name']
            stop_loss_ratio = stop_loss_logic['params']['ratio']

        start_date = pd.Timestamp(start_date).normalize()

        kis_account = self.kis.account()
        kis_balance: KisBalance = kis_account.balance()

        non_zero_stocks = [stock for stock in kis_balance.stocks if stock.qty != 0]
        kis_balance.stocks = non_zero_stocks

        # 공통된 모든 날짜 모으기
        # all_dates = set()
        all_dates = {start_date}

        for holding in kis_balance.stocks:
            
            holding_dict = {
                'symbol': holding.symbol,
                'stock_name': stock_name,
                'stock_type': stock_type,
                'timestamp_str': "",
                'close_price': 0,
                'total_quantity': 0,
                'avg_price': 0,
                'total_buy_cost': 0,
                'take_profit_logic': {
                    'name': take_profit_logic_name,
                    'ratio': take_profit_ratio,
                    'max_close_price': 0  # trailing stop loss를 위한 최고가
                },
                'stop_loss_logic': {
                    'name': stop_loss_logic_name,
                    'ratio': stop_loss_ratio,
                    'max_close_price': 0  # trailing stop loss를 위한 최고가
                },
                'trading_histories': []
            }

            global_state['account_holdings'].append(holding_dict)
        
        date_range = sorted(list(all_dates))  # 날짜 정렬

        # ✅ 매매 시작
        for idx, current_date in enumerate(date_range): 
            for holding in global_state['account_holdings']:
                symbol = holding['symbol']

                # symbols 리스트에서 해당 symbol과 일치하는 s 찾기
                s = next((s for s in symbols if s['symbol'] == symbol), None)

                if s is None:
                    print(f"❌ 해당 symbol 종목이 없습니다: {symbol}")
                    continue  # 해당 symbol 종목이 없으면 건너뜀

                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']
                stock_type = s['stock_type']

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]
    
                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next=lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next=lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price

                # ✅ 익절/손절 조건 우선 적용
                if holding['total_quantity'] > 0:
                    current_roi = ((close_price - holding['avg_price']) / holding['avg_price']) * 100

                    # 익절 조건 계산
                    if take_profit_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif take_profit_logic_name == 'trailing': # 종가 최고점 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100
                    else:
                        target_roi = current_roi

                    # 익절 조건
                    if use_take_profit and target_roi >= take_profit_ratio:

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        take_profit_hit = True
                        reason = f"익절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type = stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        # 매도 실행
                        self._trade_kis(
                            trade_type="SELL",
                            trade_quantity=trade_quantity,
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            reason=reason,
                            symbol=symbol,
                            symbol_name=stock_name,
                            ohlc_data=ohlc_data,
                            trading_bot_name=trading_bot_name,
                            target_trade_value_krw=target_trade_value_krw
                        )

                        simulation_histories.append(trading_history)

                    # 손절 조건 계산
                    if stop_loss_logic_name == 'fixed': # 고정 비율 익절
                        target_roi = current_roi
                    elif stop_loss_logic_name == 'trailing': # 최고가 기준으로 roi 계산
                        if holding['stop_loss_logic']['max_close_price'] > 0:
                            target_roi = ((close_price - holding['stop_loss_logic']['max_close_price'] ) / holding['stop_loss_logic']['max_close_price'] ) * 100 
                    else:
                        target_roi = current_roi

                    # 손절 조건
                    if use_stop_loss and target_roi <= -stop_loss_ratio:

                        trade_quantity = holding['total_quantity']

                        holding['total_quantity'] = 0
                        holding['total_buy_cost'] = 0
                        holding['avg_price'] = 0
                        holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                        stop_loss_hit = True
                        reason = f"손절 조건 충족 target_roi : ({target_roi:.2f}%), roi : ({current_roi:.2f}%)"

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type= stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='SELL',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        # 매도 실행
                        self._trade_kis(
                            trade_type="SELL",
                            trade_quantity=trade_quantity,
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            reason=reason,
                            symbol=symbol,
                            symbol_name=stock_name,
                            ohlc_data=ohlc_data,
                            trading_bot_name=trading_bot_name,
                            target_trade_value_krw=target_trade_value_krw
                        )

                        simulation_histories.append(trading_history)

                # ✅ 매도 조건 (익절/손절 먼저 처리됨, 이 블럭은 전략 로직 기반 매도)
                sell_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=sell_trading_logic,
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='SELL',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 매도 실행
                if len(sell_logic_reasons) > 0 and holding['total_quantity'] > 0:

                    trade_quantity = holding['total_quantity']

                    holding['total_quantity'] = 0
                    holding['total_buy_cost'] = 0
                    holding['avg_price'] = 0
                    holding['stop_loss_logic']['max_close_price'] = 0 # 최고가 초기화

                    reason = ""

                    trading_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=stock_name,
                        stock_type=stock_type,
                        fee=fee,
                        tax=tax,
                        revenue=revenue,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason=reason,
                        trade_type='SELL',
                        trade_quantity=trade_quantity,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=realized_pnl,
                        realized_roi=realized_roi,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    holding['trading_histories'].append(trading_history)

                    # 매도 실행
                    self._trade_kis(
                        trade_type="SELL",
                        trade_quantity=trade_quantity,
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        reason=reason,
                        symbol=symbol,
                        symbol_name=stock_name,
                        ohlc_data=ohlc_data,
                        trading_bot_name=trading_bot_name,
                        target_trade_value_krw=target_trade_value_krw
                    )

                    simulation_histories.append(trading_history)

            # 매수 로직만 확인                    
            for s in symbols:
                symbol = s['symbol']
                df = s['df']
                ohlc_data = s['ohlc_data']
                stock_name = s['stock_name']
                stock_type = s['stock_type']

                # 알맞은 종목 찾기
                holding = next((h for h in global_state['account_holdings'] if h['symbol'] == symbol), None)

                # holding이 없으면 새로 생성
                if holding is None:
                    holding = {
                        'symbol': symbol,
                        'stock_name': stock_name,
                        'stock_type': stock_type,
                        'timestamp_str': "",
                        'close_price': 0,
                        'total_quantity': 0,
                        'avg_price': 0,
                        'total_buy_cost': 0,
                        'take_profit_logic': {
                            'name': take_profit_logic_name,
                            'ratio': take_profit_ratio,
                            'max_close_price': 0  # trailing stop loss를 위한 최고가
                        },
                        'stop_loss_logic': {
                            'name': stop_loss_logic_name,
                            'ratio': stop_loss_ratio,
                            'max_close_price': 0  # trailing stop loss를 위한 최고가
                        },
                        'trading_histories': []
                    }

                    global_state['account_holdings'].append(holding)

                if not any(pd.Timestamp(c.time).tz_localize(None).normalize() == current_date for c in ohlc_data):
                    continue
                                    
                df = df[df.index <= pd.Timestamp(current_date)]
    
                # 🔍 현재 row 위치
                current_idx = len(df) - 1

                lookback_next = 5
                # ✅ 현재 시점까지 확정된 지지선만 사용
                support = self.get_latest_confirmed_support(df, current_idx=current_idx, lookback_next=lookback_next)
                resistance = self.get_latest_confirmed_resistance(df, current_idx=current_idx, lookback_next=lookback_next)
                high_trendline = indicator.get_latest_trendline_from_highs(df, current_idx=current_idx)
                
                # ✅ 아무 데이터도 없으면 조용히 빠져나가기
                if df.empty or len(df) < 2:
                    continue

                # candle_time = df.index[-1]
                candle = next(c for c in ohlc_data if pd.Timestamp(c.time).tz_localize(None) == current_date)
                close_price = float(candle.close)
                
                timestamp_str = current_date.date().isoformat()
                
                # 예수금 조회
                global_state['krw_balance'] = self._get_kis_krw_balance()

                print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,}")

                trade_quantity = 0
                realized_pnl = None
                total_buy_cost = 0
                
                buy_fee = 0
                sell_fee = 0
                tax = 0

                #익절, 손절
                take_profit_hit = False
                stop_loss_hit = False
                
                buy_logic_reasons = []
                sell_logic_reasons = []
                
                # 데이터 최신화
                holding['timestamp_str'] = timestamp_str
                holding['close_price'] = close_price
  
                # ✅ 매수 조건
                buy_logic_reasons = self._get_trading_logic_reasons(
                    trading_logics=buy_trading_logic,
                    symbol=symbol,
                    candle=candle,
                    ohlc_df=df,
                    trade_type='BUY',
                    support = support,
                    resistance = resistance,
                    high_trendline = high_trendline
                )

                # ✅ 직접 지정된 target_trade_value_krw가 있으면 사용, 없으면 비율로 계산
                if target_trade_value_krw and target_trade_value_krw > 0:
                    trade_amount = min(target_trade_value_krw, global_state['krw_balance'])
                    min_trade_value = 0 # 고정 금액의 경우 min_trade_value는 무시
                else:
                    trade_ratio = trade_ratio if trade_ratio is not None else 100
                    
                    # 현재 총 자산을 구하기 위한 로직 
                    total_market_value = 0
                    for h in global_state['account_holdings']:
                        market_value = h['avg_price'] * h['total_quantity']
                        total_market_value += market_value

                    total_balance = global_state['krw_balance'] + total_market_value
                    trade_amount = min(total_balance * (trade_ratio / 100), global_state['krw_balance'])

                # ✅ 매수 실행
                if len(buy_logic_reasons) > 0 and min_trade_value <= trade_amount:
                    buy_quantity = math.floor(trade_amount / close_price)
                    cost = buy_quantity * close_price
                    fee = cost * 0.00014
                    tax = 0
                    total_buy_cost = cost + fee
                    
                    # 매수 금액이 예수금보다 작거나 같을 때만 매수
                    if buy_quantity > 0 and total_buy_cost <= global_state['krw_balance']:

                        global_state['krw_balance'] -= total_buy_cost
                        holding['total_buy_cost'] += total_buy_cost
                        holding['total_quantity'] += buy_quantity
                        holding['avg_price'] = holding['total_buy_cost'] / holding['total_quantity']

                        if holding['stop_loss_logic']['max_close_price'] < close_price:
                            holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트

                        revenue = 0
                        realized_pnl = 0
                        realized_roi = (realized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0
                        unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                        unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                        trade_quantity = buy_quantity

                        reason = ""

                        trading_history = self._create_trading_history(
                            symbol=symbol,
                            stock_name=stock_name,
                            stock_type=stock_type,
                            fee=fee,
                            tax=tax,
                            revenue=revenue,
                            timestamp=current_date,
                            timestamp_str=timestamp_str,
                            reason=reason,
                            trade_type='BUY',
                            trade_quantity=trade_quantity,
                            avg_price=holding['avg_price'],
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            realized_pnl=realized_pnl,
                            realized_roi=realized_roi,
                            unrealized_pnl=unrealized_pnl,
                            unrealized_roi=unrealized_roi,
                            krw_balance=global_state['krw_balance'],
                            total_quantity=holding['total_quantity'],
                            total_buy_cost=holding['total_buy_cost'],
                            close_price=close_price
                        )

                        holding['trading_histories'].append(trading_history)

                        # 매도 실행
                        self._trade_kis(
                            trade_type="BUY",
                            trade_quantity=trade_quantity,
                            buy_logic_reasons=buy_logic_reasons,
                            sell_logic_reasons=sell_logic_reasons,
                            take_profit_hit=take_profit_hit,
                            stop_loss_hit=stop_loss_hit,
                            reason=reason,
                            symbol=symbol,
                            symbol_name=stock_name,
                            ohlc_data=ohlc_data,
                            trading_bot_name=trading_bot_name,
                            target_trade_value_krw=target_trade_value_krw
                        )

                        simulation_histories.append(trading_history)
                
                # holding['trading_histories'] 를 활용해서 이미 매매가 이루어진 경우를 확인
                already_traded_yn = any(
                    history['timestamp_str'] == timestamp_str and history['trade_type'] in ('BUY', 'SELL')
                    for history in holding['trading_histories']
                )

                # 매매가 이루어지지 않은 경우
                if already_traded_yn is False:

                    unrealized_pnl = (close_price - holding['avg_price']) * holding['total_quantity']
                    unrealized_roi = (unrealized_pnl / holding['total_buy_cost']) * 100 if holding['total_buy_cost'] > 0 else 0

                    # 최고가 trailing 하고 있을 경우
                    if holding['stop_loss_logic']['max_close_price'] > 0 and holding['stop_loss_logic']['max_close_price'] < close_price:
                        holding['stop_loss_logic']['max_close_price'] = close_price # 최고가 업데이트
                        
                    # 아무런 매수 없이 히스토리만 생성
                    simulation_history = self._create_trading_history(
                        symbol=symbol,
                        stock_name=stock_name,
                        stock_type=stock_type,
                        fee=0,
                        tax=0,
                        revenue=0,
                        timestamp=current_date,
                        timestamp_str=timestamp_str,
                        reason="",
                        trade_type=None,
                        trade_quantity=0,
                        avg_price=holding['avg_price'],
                        buy_logic_reasons=buy_logic_reasons,
                        sell_logic_reasons=sell_logic_reasons,
                        take_profit_hit=take_profit_hit,
                        stop_loss_hit=stop_loss_hit,
                        realized_pnl=0,
                        realized_roi=0,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_roi=unrealized_roi,
                        krw_balance=global_state['krw_balance'],
                        total_quantity=holding['total_quantity'],
                        total_buy_cost=holding['total_buy_cost'],
                        close_price=close_price
                    )

                    simulation_histories.append(simulation_history)

                    print(f"💰 시뮬 중: {symbol} / 날짜: {timestamp_str} / 사용가능한 예수금: {global_state['krw_balance']:,} / 거래 없음")

        return None


    def _get_kis_krw_balance(self):

        # 1원 단위로 조회
        kis_account = self.kis.account()
        max_retries = 5

        kis_krw_balance = 0

        for attempt in range(0, max_retries):
            try:
                orderable_amount: KisOrderableAmount = kis_account.orderable_amount(
                    market="KRX",
                    price=1,
                    symbol="039200"
                )

                kis_krw_balance = int(orderable_amount.qty)
                break

            except Exception as e:
                print(f"[{attempt+1}/{max_retries}] 주문 가능 금액 조회 실패: {e}")
                time.sleep(1)  # 1초 대기 후 재시도

        return kis_krw_balance
                

    def _get_trading_logic_reasons(self, trading_logics, symbol, candle, ohlc_df, support, resistance, high_trendline, trade_type = 'BUY', rsi_buy_threshold = 30, rsi_sell_threshold = 70):

        signal_reasons = []

        if trade_type == 'BUY':
            for trading_logic in trading_logics:
                buy_yn = False # 각 로직에 대한 매수 신호 초기화
                            
                if trading_logic == 'rsi_trading':            
                    buy_yn, _ = logic.rsi_trading(candle, ohlc_df['rsi'], symbol, rsi_buy_threshold, rsi_sell_threshold)

                elif trading_logic == 'macd_trading':
                    buy_yn, _ = logic.macd_trading(candle, ohlc_df, symbol)
                                            
                elif trading_logic == 'mfi_trading':
                    buy_yn, _ = logic.mfi_trading(ohlc_df, symbol)    
                    
                elif trading_logic == 'stochastic_trading':
                    buy_yn, _ = logic.stochastic_trading(ohlc_df, symbol)
                    
                elif trading_logic == 'rsi+mfi':
                    buy_yn1, _ = logic.mfi_trading(ohlc_df)
                    buy_yn2, _ = logic.rsi_trading(candle, ohlc_df['rsi'], symbol, rsi_buy_threshold, rsi_sell_threshold)
                    buy_yn = buy_yn1 and buy_yn2
                    
                elif trading_logic == 'ema_breakout_trading':
                    buy_yn, _ = logic.ema_breakout_trading(ohlc_df, symbol)
                            
                elif trading_logic == 'ema_breakout_trading2':
                    buy_yn, _ = logic.ema_breakout_trading2(ohlc_df, symbol)
                    
                elif trading_logic == 'trend_entry_trading':
                    buy_yn, _ = logic.trend_entry_trading(ohlc_df)
                
                elif trading_logic == 'trend_entry_trading_20ema':
                    buy_yn, _ = logic.trend_entry_trading_v2(ohlc_df, period=20)
                
                elif trading_logic == 'trend_entry_trading_60ema':
                    buy_yn, _ = logic.trend_entry_trading_v2(ohlc_df, period=60)
                
                elif trading_logic == 'trend_entry_trading_120ema':
                    buy_yn, _ = logic.trend_entry_trading_v2(ohlc_df, period=120)
                
                elif trading_logic == 'trend_entry_trading_200ema':
                    buy_yn, _ = logic.trend_entry_trading_v2(ohlc_df, period=200)
                
                elif trading_logic == 'trend_entry_trading_0_to_6':
                    buy_yn, _ = logic.trend_entry_trading(ohlc_df, lower_threshold_ratio=0.0, upper_threshold_ratio= 0.06)
                    
                elif trading_logic == 'bottom_rebound_trading':
                    buy_yn, _ = logic.bottom_rebound_trading(ohlc_df)
                    
                elif trading_logic == 'sma_breakout_trading':
                    buy_yn, _ = logic.sma_breakout_trading(ohlc_df, symbol, resistance)
                    
                elif trading_logic == 'ema_breakout_trading3':
                    buy_yn, _ = logic.ema_breakout_trading3(ohlc_df)
                    
                elif trading_logic == 'ema_crossover_trading':
                    buy_yn, _ = logic.ema_crossover_trading(ohlc_df, resistance)

                elif trading_logic == 'ema_crossover_trading_v2':
                    buy_yn, _ = logic.ema_crossover_trading_v2(ohlc_df, resistance)
                    
                elif trading_logic == 'anti_retail_ema_entry':
                    buy_yn, _ = logic.anti_retail_ema_entry(ohlc_df)
                    
                elif trading_logic == 'trendline_breakout_trading':
                    buy_yn, _ = logic.trendline_breakout_trading(ohlc_df, resistance)
                    
                elif trading_logic == 'should_buy':
                    buy_yn, _ = logic.should_buy(ohlc_df, high_trendline, resistance)
                    
                elif trading_logic == 'should_buy_break_high_trend':
                    buy_yn, _ = logic.should_buy_break_high_trend(ohlc_df)
                    
                elif trading_logic == 'weekly_trading':
                    buy_yn, _ = logic.weekly_trading(ohlc_df, resistance)
                    
                elif trading_logic == 'new_trading':
                    buy_yn, _ = logic.new_trading(ohlc_df)
                    
                elif trading_logic == 'sma_crossover_trading':
                    buy_yn, _ = logic.sma_crossover_trading(ohlc_df, resistance)
                    
                elif trading_logic == 'wma_crossover_trading':
                    buy_yn, _ = logic.wma_crossover_trading(ohlc_df, resistance)
                    
                elif trading_logic == 'ema_breakout_trading2':
                    buy_yn, _ = logic.ema_breakout_trading2(ohlc_df, resistance)
                    
                elif trading_logic == 'day120_trend_line':
                    buy_yn, _ = logic.day120_trend_line(ohlc_df)
                    
                elif trading_logic == 'day120_trend_line_2':
                    buy_yn, _ = logic.day120_trend_line_2(ohlc_df)
                    
                elif trading_logic == 'new_trend_entry':
                    buy_yn, _ = logic.new_trend_entry(ohlc_df)
                    
                elif trading_logic == 'new_trend_entry2':
                    buy_yn, _ = logic.new_trend_entry2(ohlc_df)
                    
                elif trading_logic == 'congestion_trading':
                    buy_yn, _ = logic.congestion_trading(ohlc_df)   

                elif trading_logic == 'combined_new_trend_entry':
                    buy_yn, _ = logic.combined_new_trend_entry(ohlc_df)

                elif trading_logic == 'detect_large_volume_trades':
                    buy_yn, _ = logic.detect_large_volume_trades(ohlc_df)

                elif trading_logic == 'all_time_high_trading':
                    buy_yn, _ = logic.all_time_high_trading(ohlc_df, days=10, period=20)

                elif trading_logic == 'williams_trading':
                    buy_yn, _ = logic.williams_trading(ohlc_df) 
                
                if buy_yn:
                    signal_reasons.append(trading_logic)
        else:
            for trading_logic in trading_logics:
                result = False

                if trading_logic == 'rsi_trading':
                    _, result = logic.rsi_trading(candle, ohlc_df['rsi'], symbol, rsi_buy_threshold, rsi_sell_threshold)

                elif trading_logic == 'rsi_trading2':
                    _, result = logic.rsi_trading2(candle, ohlc_df['rsi'], symbol, rsi_buy_threshold, rsi_sell_threshold)

                elif trading_logic == 'mfi_trading':
                    _, result = logic.mfi_trading(ohlc_df, symbol)

                elif trading_logic == 'stochastic_trading':
                    _, result = logic.stochastic_trading(ohlc_df, symbol)

                elif trading_logic == 'macd_trading':
                    _, result = logic.macd_trading(candle, ohlc_df, symbol)

                elif trading_logic == 'rsi+mfi':
                    _, r1 = logic.mfi_trading(ohlc_df)
                    _, r2 = logic.rsi_trading(candle, ohlc_df['rsi'], symbol, rsi_buy_threshold, rsi_sell_threshold)
                    result = r1 and r2

                elif trading_logic == 'top_reversal_sell_trading':
                    _, result = logic.top_reversal_sell_trading(ohlc_df)

                elif trading_logic == 'downtrend_sell_trading':
                    _, result = logic.downtrend_sell_trading(ohlc_df)

                elif trading_logic == 'should_sell':
                    _, result = logic.should_sell(ohlc_df)

                elif trading_logic == 'break_prev_low':
                    _, result = logic.break_prev_low(ohlc_df)
                    
                elif trading_logic == 'sell_on_support_break':
                    _, result = logic.sell_on_support_break(ohlc_df)
                    
                elif trading_logic == 'horizontal_low_sell':
                    _, result = logic.horizontal_low_sell(ohlc_df)
                    
                elif trading_logic == 'sell_on_5ema_break':
                    _, result = logic.sell_on_ema_break(ohlc_df, period=5)

                elif trading_logic == 'sell_on_10ema_break':
                    _, result = logic.sell_on_ema_break(ohlc_df, period=10) 

                elif trading_logic == 'sell_on_20ema_break':
                    _, result = logic.sell_on_ema_break(ohlc_df, period=20)

                elif trading_logic == 'ema_cross_sell_5short_10long':
                    _, result = logic.ema_cross_sell(ohlc_df, period_short=5, period_long=10)                        

                # ✅ 조건 만족하면 즉시 기록
                if result:
                    signal_reasons.append(trading_logic)
        
        return signal_reasons


    def _trade_kis(self, trade_type, buy_logic_reasons, sell_logic_reasons, take_profit_hit, stop_loss_hit, reason, symbol, symbol_name, ohlc_data, trading_bot_name, target_trade_value_krw, trade_quantity):
        
        # trade_quantity = 1
        reason_str = f"매수 로직 : {buy_logic_reasons}, 매도 로직 : {sell_logic_reasons}, 익절 : {take_profit_hit}, 손절 : {stop_loss_hit}, 이유 : {reason}"
        
        price = ohlc_data[-1].close  # 현재 종가로 매매
        # 매매 요청
        self._trade_place_order(symbol, symbol_name, target_trade_value_krw, trade_type, price, trade_quantity, trading_bot_name)

        # 결과 웹훅 전송
        webhook.send_discord_webhook(
            f"[reason:{reason_str}], {symbol_name} 매수가 완료되었습니다. 매수금액 : {price}KRW",
            "trading"
        )
        
        # 매매 기록 DB 저장
        self._insert_trading_history(
            reason_str, trade_type, trading_bot_name, price, trade_quantity, symbol, symbol_name
        )
        
        # if trade_type == "BUY":
   
        #     self._trade_place_order(symbol, symbol_name, target_trade_value_krw, order_type, trading_bot_name)

        #     # 매수 주문은 특정 로직에서만 실행
        #     # if 'trend_entry_trading' in trading_logic or 'ema_breakout_trading3' in trading_logic or 'sma_breakout_trading' in trading_logic:
        #     #     self._trade_place_order(symbol, symbol_name, target_trade_value_krw, order_type, trading_bot_name)
 
        #     self._insert_trading_history(
        #         trading_logic, trade_type, trading_bot_name, ohlc_data[-1].close, 
        #         quantity, symbol, symbol_name
        #     )
        
        # if sell_yn:
        #     order_type = 'sell'

        #     self._trade_place_order(symbol, symbol_name, target_trade_value_krw, order_type, trading_bot_name)
            
        #     # trade history 에 추가
        #     position = 'SELL'
        #     quantity = 1 # 임시

        #     self._insert_trading_history(trading_logic, position, trading_bot_name, ohlc_data[-1].close,
        #         quantity, symbol, symbol_name
        #     )


    def _insert_trading_history(self, trading_logic, position, trading_bot_name, price, quantity, symbol, symbol_name, data_type='test'):
        
        dynamodb_executor = DynamoDBExecutor()
        # 한국 시간대
        kst = timezone("Asia/Seoul")
        # 현재 시간을 KST로 변환
        current_time = datetime.now(kst)
        created_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성

        data_model = TradingHistory(
            trading_bot_name=trading_bot_name,
            created_at=created_at,
            updated_at=None,
            trading_logic=trading_logic,
            trade_date=created_at,
            symbol=symbol,
            symbol_name=symbol_name,
            position=position,
            price=float(price),
            quantity=float(quantity),
            data_type=data_type
        )

        result = dynamodb_executor.execute_save(data_model)
        print(f'execute_save 결과 = {result}')

        return result
    

    def _insert_auto_trading(self, trading_bot_name,trading_logic,symbol,symbol_name,position,price,quantity):
        # 한국 시간대 기준 timestamp
        kst = timezone("Asia/Seoul")
        now = datetime.now(kst)
        created_at = int(now.timestamp() * 1000)
        trade_date = int(now.strftime("%Y%m%d"))

        data_model = AutoTrading(
            trading_bot_name=trading_bot_name,
            created_at=created_at,
            updated_at=None,
            trading_logic=trading_logic,
            trade_date=trade_date,
            symbol=symbol,
            symbol_name=symbol_name,
            position=position,
            price=float(price),
            quantity=float(quantity)
        )

        dynamodb_executor = DynamoDBExecutor()
        result = dynamodb_executor.execute_save(data_model)
        print(f'[자동매매 로그 저장] execute_save 결과 = {result}')


    def _upsert_account_balance(self, trading_bot_name):
        kst = timezone("Asia/Seoul")
        updated_at = int(datetime.now(kst).timestamp() * 1000)

        holdings = self._get_holdings_with_details()
        
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
    
    
    def place_order(self, symbol, symbol_name, qty, order_type, buy_price=None, sell_price=None, deposit = None, trading_bot_name = 'schedulerbot'):
        """주식 매수/매도 주문 함수
        Args:
            deposit : 예수금
            symbol (str): 종목 코드
            qty (int): 주문 수량
            price (int, optional): 주문 가격. 지정가 주문 시 필요
            order_type (str): "buy" 또는 "sell"
        """
        try:
            # 종목 객체 가져오기
            stock = self.kis.stock(symbol)

            # 매수/매도 주문 처리
            if order_type == "buy":
                if buy_price:
                    order = stock.buy(price=buy_price, qty=qty)  # price 값이 있으면 지정가 매수
                else:
                    order = stock.buy(qty=qty)  # 시장가 매수
                message = f"📈 매수 주문 완료! bot: {trading_bot_name} 종목: {symbol}, 종목명: {symbol_name} 수량: {qty}, 가격: {'시장가' if not buy_price else buy_price}"
            elif order_type == "sell":
                if sell_price:
                    order = stock.sell(price=sell_price)  # 지정가 매도
                else:
                    order = stock.sell()  # 시장가 매도
                message = f"📉 매도 주문 완료! bot: {trading_bot_name} 종목: {symbol}, 종목명: {symbol_name} 수량: {qty}, 가격: {'시장가' if not sell_price else sell_price}"
            else:
                raise ValueError("Invalid order_type. Must be 'buy' or 'sell'.")

            # 디스코드로 주문 결과 전송
            webhook.send_discord_webhook(message, "trading")

            return order
        
        except Exception as e:
            error_message = f"주문 처리 중 오류 발생: {e}\n 예수금 : {deposit}, "
            print(error_message)
            webhook.send_discord_webhook(error_message, "trading")



    def _get_quote(self, symbol):
        quote: KisQuote = self.kis.stock(symbol).quote()
        return quote


    def _trade_place_order(self, symbol, symbol_name, target_trade_value_krw, order_type, price, trade_quantity, trading_bot_name):
        # 호가 조회
        # quote = self._get_quote(symbol=symbol)
        # buy_price = None  # 시장가 매수
        # sell_price = None # 시장가 매도

        if order_type == 'BUY':
            # if not self.virtual:
            #     psbl_order_info = self.inquire_psbl_order(symbol)
            #     if psbl_order_info is None:
            #         print(f"[{datetime.now()}] ❌ 주문가능금액 조회 실패")
            #         message = f"[{datetime.now()}] ❌ 주문가능금액 조회 실패: {symbol}"
            #         return

            #     max_buy_amt = int(psbl_order_info['output']['nrcvb_buy_amt']) # 최대 매수 가능 금액
            #     max_buy_qty = int(psbl_order_info['output']['max_buy_qty'])      # 최대 매수 가능 수량
            #     print(f"max_buy_amt: {max_buy_amt}, max_buy_qty: {max_buy_qty}, target_trade_value_krw: {target_trade_value_krw}")
                
            #         # ✅ 매수 가능 금액이 50만원 미만이면 매수 생략
            #     if max_buy_amt < 500_000:
            #         print(f"[{datetime.now()}] 🚫 매수 생략: 매수 가능 금액이 50만원 미만 ({max_buy_amt:,}원)")
            #         message = f"[{datetime.now()}] 🚫 매수 생략: 매수 가능 금액이 50만원 미만 ({max_buy_amt:,}원): {symbol}"
            #         return
    
            #     # ✅ 수수료 포함하여 수량 계산
            #     adjusted_price = price * (1 + 0.00014)  # 수수료 포함 단가

            #     # 1. 원래 요청 금액과 최대 가능 금액 중 작은 금액 선택
            #     actual_trade_value = min(target_trade_value_krw, max_buy_amt)
        
            #     if actual_trade_value == target_trade_value_krw:
            #         qty = math.floor(actual_trade_value / adjusted_price)
            #         #qty = qty - 1 #개수를 1개 줄여서 매수 실패 방지
            #     else:
            #         qty = max_buy_qty
            #         qty = max(0, qty - 1) #개수를 1개 줄여서 매수 실패 방지
                    
            # else:  # ✅ 모의투자인 경우 psbl 조회 건너뛰고 target_trade_value로만 계산
            #     adjusted_price = price * (1 + 0.00014)
            #     qty = math.floor(target_trade_value_krw / adjusted_price)
            #     print(f"[{datetime.now()}] (모의투자) 계산된 매수 수량: {qty} (단가: {adjusted_price:.2f})")
            #     message = f"[{datetime.now()}] (모의투자) 계산된 매수 수량: {qty} (단가: {adjusted_price:.2f}) - {symbol}"

            # if qty <= 0:
            #     print(f"[{datetime.now()}] 🚫 수량이 0입니다. 매수 생략: {symbol}")
            #     message = f"[{datetime.now()}] 🚫 수량이 0입니다. 매수 생략: {symbol}"
            #     return

            order_amount = trade_quantity * price
            print(f"[{datetime.now()}] ✅ 자동 매수 실행: bot: {trading_bot_name} 종목 {symbol_name}, 수량 {trade_quantity}주, 주문 금액 {order_amount:,}원")
            message = f"[{datetime.now()}] ✅ 자동 매수 실행: bot: {trading_bot_name} 종목 {symbol_name}, 수량 {trade_quantity}주, 주문 금액 {order_amount:,}원"
            try:
                self.place_order(
                    symbol=symbol,
                    symbol_name = symbol_name,
                    qty=trade_quantity,
                    order_type="buy",
                    buy_price=price,
                    trading_bot_name = trading_bot_name
                )
            except Exception as e:
                print(f"[{datetime.now()}] ❌ 매수 실패: {e}")
                message = f"[{datetime.now()}] ❌ 매수 실패: {e} - {symbol}"
            
        elif order_type == 'SELL':
            # ✅ 보유 종목에서 해당 symbol 찾아서 수량 확인
            # holdings = self._get_holdings_with_details()
            # holding = next((item for item in holdings if item['symbol'] == symbol), None)

            # if not holding:
            #     print(f"[{datetime.now()}] 🚫 매도 생략: {symbol} 보유 수량 없음")
            #     message = f"[{datetime.now()}] 🚫 매도 생략: {symbol} 보유 수량 없음"
            #     return

            # qty = holding[1] #수량을 저장, holding[0]은 종목 코드

            print(f"[{datetime.now()}] ✅ 자동 매도 실행: bot: {trading_bot_name} 종목 {symbol_name}, 수량 {trade_quantity}주 (시장가 매도)")
            message = f"[{datetime.now()}] ✅ 자동 매도 실행: bot: {trading_bot_name} 종목 {symbol_name}, 수량 {trade_quantity}주 (시장가 매도)"
            try:
                self.place_order(
                    symbol=symbol,
                    symbol_name = symbol_name,
                    qty=trade_quantity,
                    order_type='sell',
                    sell_price=price,
                    trading_bot_name = trading_bot_name
                )
                
            except Exception as e:
                print(f"[{datetime.now()}] ❌ 매도 실패: {e}")
                message = f"[{datetime.now()}] ❌ 매도 실패: {e} - {symbol}"

        else:
            print(f"[{datetime.now()}] ❌ 잘못된 주문 타입입니다: {order_type}")
            message = f"[{datetime.now()}] ❌ 잘못된 주문 타입입니다: {order_type} - {symbol}"
            
        webhook.send_discord_webhook(message, "trading")


    def _get_holdings_with_details(self):

        account = self.kis.account()
        balance = account.balance()

        holdings = []
        for stock in balance.stocks:
            if stock.qty > 0:
                holding = {
                    'symbol': stock.symbol,
                    'symbol_name': stock.name,
                    'market': stock.market,
                    'quantity': int(stock.qty),
                    'price': int(stock.price),             # 평균 단가
                    'amount': int(stock.amount),           # 평가 금액
                    'profit': int(stock.profit),           # 평가 손익
                    'profit_rate': float(stock.profit_rate), # 수익률 (ex: 2.78)
                }
                holdings.append(holding)

        return holdings

    def update_roi(self, trading_bot_name):
                # ✅ 손익 조회
                
        def round_half(x):
            """0.5 단위 반올림 함수"""
            return round(x * 2) / 2
        
        account = self.kis.account()
        
        # ✅ 실현 손익 조회
        profits: KisOrderProfits = account.profits(start=date(2023, 8, 1), end=date.today())
        realized_pnl = float(profits.profit)                # 실현 손익
        realized_buy_amt = float(profits.buy_amount)        # 실현 매입 금액

        # ✅ 미실현 손익 조회
        balance: KisBalance = account.balance()
        unrealized_pnl = float(balance.profit)     # 평가손익
        holding_buy_amt = float(balance.purchase_amount)           # 현재 보유 주식 매입 금액
        unrealized_roi_raw = float(balance.profit_rate)     # 미실현 수익률 (원래 %)

        # ✅ 수익률 계산
        realized_roi = (realized_pnl / realized_buy_amt) * 100 if realized_buy_amt > 0 else 0.0
        total_pnl = realized_pnl + unrealized_pnl
        total_buy_amt = realized_buy_amt + holding_buy_amt
        total_roi = (total_pnl / total_buy_amt) * 100 if total_buy_amt > 0 else 0.0

        # ✅ 날짜는 YYYY-MM-DD 기준 (시간 X)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # ✅ 기록할 데이터
        record = {
            "date": today_str,
            "bot_name": trading_bot_name,
            "realized_pnl": realized_pnl,
            "realized_buy_amt": realized_buy_amt,
            "realized_roi": round_half(realized_roi),
            "unrealized_pnl": unrealized_pnl,
            "unrealized_roi": round_half(unrealized_roi_raw),
            "holding_buy_amt": holding_buy_amt,
            "total_pnl": total_pnl,
            "total_buy_amt": total_buy_amt,
            "total_roi": round_half(total_roi)
        }

        # ✅ 저장할 CSV 파일
        csv_file = "profits_history.csv"

        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)

            # 날짜 + 봇 이름 중복 시 덮어쓰기
            df = df[~((df['date'] == today_str) & (df['bot_name'] == trading_bot_name))]
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        else:
            df = pd.DataFrame([record])

        # ✅ 저장
        df.to_csv(csv_file, index=False)
        print(f"✅ 수익률 기록 저장 완료 ({csv_file})")
        
    # 컷 로스 (손절)
    def cut_loss(self, target_trade_value_usdt):
        pass
    
    def inquire_psbl_order(self , symbol):
        domain = "https://openapivts.koreainvestment.com:29443" if self.virtual else "https://openapi.koreainvestment.com:9443"
        url = f"{domain}/uapi/domestic-stock/v1/trading/inquire-psbl-order"

        headers = {
            "authorization": str(self.kis.token),
            "appkey": self.app_key,
            "appsecret": self.secret_key,
            "tr_id": "VTTC8908R" if self.virtual else "TTTC8908R",  # 모의/실전 구분
        }

        body = {
            "CANO": self.account,                    # 계좌번호 앞 8자리
            "ACNT_PRDT_CD": '01',    # 계좌상품코드 (보통 "01")
            "PDNO":symbol,                    # 종목코드
            "ORD_UNPR": "0",                 # 주문단가, 0이면 시장가 기준
            "ORD_DVSN": "01",                # 주문구분 (보통 시장가: 01)
            "CMA_EVLU_AMT_ICLD_YN": "N",     # CMA 평가금액 포함 여부
            "OVRS_ICLD_YN": "N"              # 해외주식 포함 여부
        }

        response = requests.get(url, headers=headers, params=body)
        
        try:
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print("❌ API 호출 실패:", e)
            return None
        
    def get_investor_trend_estimate(self, symbol):
        """
        한국투자증권 실전투자 API - 종목별 외인기관 추정가 집계 요청

        Parameters:
            symbol (str): 종목코드 (e.g. "005930")
            access_token (str): 발급받은 OAuth Access Token
            app_key (str): 발급받은 App Key
            app_secret (str): 발급받은 App Secret

        Returns:
            dict: 응답 JSON 데이터
            1: 09시 30분 입력
            2: 10시 00분 입력
            3: 11시 20분 입력
            4: 13시 20분 입력
            5: 14시 30분 입력
        """

        # 실전 투자용 도메인 및 URL
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/investor-trend-estimate"

        # HTTP Headers
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": str(self.kis.token),
            "appkey": self.app_key,
            "appsecret": self.secret_key,
            "tr_id": "HHPTJ04160200",
            "custtype": "P",  # 개인 고객용
        }

        # Query Parameters
        params = {
            "MKSC_SHRN_ISCD": symbol  # 종목코드
        }

        # API 요청
        response = requests.get(url, headers=headers, params=params)

        # 결과 확인
        if response.status_code == 200:
            return response.json()
        else:
            print("❌ 요청 실패:", response.status_code, response.text)
            return None

    def calculate_trade_value_from_fake_qty(self, api_response: dict, close_price: float, symbol) -> int:
        """
        종가 * sum_fake_ntby_qty(bsob_hour_gb = '5')로 거래대금을 계산

        Parameters:
            api_response (dict): API 응답 결과
            close_price (float): 해당 시점의 종가

        Returns:
            int: 계산된 거래대금 (원 단위)
        """
        api_response = self.get_investor_trend_estimate(symbol)
        
        if api_response is None:
            print(f"❌ API 응답이 None입니다: symbol={symbol}")
            return 0
        
        try:
            output2 = api_response.get("output2", [])
            for item in output2:
                if item.get("bsop_hour_gb") == "5":
                    raw_qty = item.get("sum_fake_ntby_qty", "0") #만약 key값이 없다면 0으로 반환
                    # 부호 처리 포함 정수 변환
                    qty = int(raw_qty.replace("-", "-").lstrip("0") or "0")
                    trade_value = qty * close_price
                    return trade_value
            
            return 0
        except Exception as e:
            print(f"❌ 계산 오류: {e}")
            return 0
        
    def get_latest_confirmed_support(self, df, current_idx, lookback_next=5):
        """
        현재 시점(i)에서 확정된 지지선만 가져오기
        - i보다 최소 lookback_next 만큼 이전에 확정된 것만 허용
        """
        max_confirmed_idx = current_idx - lookback_next
        if max_confirmed_idx <= 0:
            return None

        valid = df.iloc[:max_confirmed_idx][df['horizontal_low'].notna()]
        if valid.empty:
            return None

        return valid.iloc[-1]['horizontal_low']

    def get_latest_confirmed_resistance(self, df, current_idx, lookback_next=5):
        """
        현재 시점(i)에서 확정된 저항선(horizontal_high)만 가져오기
        - i보다 최소 lookback_next 만큼 이전에 확정된 고점만 허용
        """
        max_confirmed_idx = current_idx - lookback_next
        if max_confirmed_idx <= 0:
            return None

        valid = df.iloc[:max_confirmed_idx][df['horizontal_high'].notna()]
        if valid.empty:
            return None

        return valid.iloc[-1]['horizontal_high']
    
    def get_foreign_institution_net_buy_summary(self, market_code: str = "KSQ", industry: str = "1001"):
        """
        한국투자증권 실전투자 API - 국내기관/외국인 매매 종목 가집계

        Parameters:
            symbol (str): 종목코드 (e.g. "005930")

        Returns:
            dict: 응답 JSON 데이터

        예시:
            - 외국인 순매수 금액순: FID_DIV_CLS_CODE=0, FID_RANK_SORT_CLS_CODE=D
            - 기관 매도 수량순: FID_DIV_CLS_CODE=2, FID_RANK_SORT_CLS_CODE=Q
        """

        # 실전 도메인
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market"

        # 요청 헤더
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": str(self.kis.token),
            "appkey": self.app_key,
            "appsecret": self.secret_key,
            "tr_id": "FHPTJ04030000",
            "custtype": "P",  # 개인
        }

        # 쿼리 파라미터
        params = {
            "fid_input_iscd": market_code,   # 코스닥150: KQI
            "fid_input_iscd_2": industry,
        }

        # 요청
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print("❌ 요청 실패:", response.status_code, response.text)
            return None

        data = response.json()
        print(f"data: {data}")
        
        output_list = data.get('output', [])
        if not output_list:
            print("⚠️ output 리스트가 비어 있습니다.")
            return None

        output = output_list[0]
        # 주체명과 해당 키 매핑
        target_keys = {
            '외국인': 'frgn_ntby_tr_pbmn',
            '개인': 'prsn_ntby_tr_pbmn',
            '기관계': 'orgn_ntby_tr_pbmn',
            '증권': 'scrt_ntby_tr_pbmn',
            '투자신탁': 'ivtr_ntby_tr_pbmn',
            '사모펀드': 'pe_fund_ntby_tr_pbmn',
            '은행': 'bank_ntby_tr_pbmn',
            '보험': 'insu_ntby_tr_pbmn',
            '종금': 'mrbn_ntby_tr_pbmn',
            '기금': 'fund_ntby_tr_pbmn',
            '기타단체': 'etc_orgt_ntby_tr_pbmn',
            '기타법인': 'etc_corp_ntby_tr_pbmn'
        }

        result = {}
        for name, key in target_keys.items():
            value = output.get(key)
            if value is not None:
                result[name] = value

        return result
        
    def map_investor_estimates(self, data: dict) -> list:
        """
        get_investor_trend_estimate 응답에서 외국인, 기관, 총매수량을 시간별로 추출 및 정리

        Parameters:
            data (dict): API 응답 JSON

        Returns:
            list[dict]: [{'시간': '09:30', '외국인': -51000, '기관': 0, '총계': -51000}, ...]
        """
        time_map = {
            '1': '09:30',
            '2': '10:00',
            '3': '11:20',
            '4': '13:20',
            '5': '14:30',
        }

        result = []
        for row in data.get('output2', []):
            result.append({
                '시간': time_map.get(row['bsop_hour_gb'], row['bsop_hour_gb']),
                '외국인': int(row['frgn_fake_ntby_qty']),
                '기관': int(row['orgn_fake_ntby_qty']),
                '총계': int(row['sum_fake_ntby_qty'])
            })
        return result
    
    def get_short_sale_daily_trend(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        market_code: str = "J"  # 코스피: J, 코스닥: Q
    ):
        """
        한국투자증권 실전투자 API - 국내주식 공매도 일별추이 조회

        Parameters:
            symbol (str): 종목코드 (6자리 문자열, 예: "005930")
            start_date (str): 조회 시작일 (YYYYMMDD)
            end_date (str): 조회 종료일 (YYYYMMDD)
            market_code (str): 시장 분류 코드 ("J": 코스피, "Q": 코스닥)

        Returns:
            dict: 일별 공매도 데이터 목록 또는 None
        """

        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/daily-short-sale"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": str(self.kis.token),
            "appkey": self.app_key,
            "appsecret": self.secret_key,
            "tr_id": "FHPST04830000",
            "custtype": "P",  # 개인
        }

        params = {
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_COND_MRKT_DIV_CODE": market_code,
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print("❌ 요청 실패:", response.status_code, response.text)
            return None

        data = response.json()
        output2 = data.get("output2", [])

        if not output2:
            print("⚠️ output2가 비어 있습니다.")
            return None

        # ✅ 영문 → 한글 필드 매핑
        field_map = {
            "stck_bsop_date": "영업일자",
            "stck_clpr": "종가",
            "prdy_vrss": "전일대비",
            "prdy_vrss_sign": "전일대비부호",
            "prdy_ctrt": "전일대비율",
            "acml_vol": "누적거래량",
            "stnd_vol_smtn": "기준거래량합계",
            "ssts_cntg_qty": "공매도체결수량",
            "ssts_vol_rlim": "공매도거래량비중",
            "acml_ssts_cntg_qty": "누적공매도체결수량",
            "acml_ssts_cntg_qty_rlim": "누적공매도수량비중",
            "acml_tr_pbmn": "누적거래대금",
            "stnd_tr_pbmn_smtn": "기준거래대금합계",
            "ssts_tr_pbmn": "공매도거래대금",
            "ssts_tr_pbmn_rlim": "공매도거래대금비중",
            "acml_ssts_tr_pbmn": "누적공매도거래대금",
            "acml_ssts_tr_pbmn_rlim": "누적공매도거래대금비중",
            "stck_oprc": "시가",
            "stck_hgpr": "고가",
            "stck_lwpr": "저가",
            "avrg_prc": "공매도평균가격"
        }

        # ✅ 리스트 → DataFrame
        df = pd.DataFrame(output2)

        # ✅ 컬럼명 매핑
        df.rename(columns=field_map, inplace=True)

        # ✅ 날짜 컬럼 datetime으로 변환
        df["영업일자"] = pd.to_datetime(df["영업일자"], format="%Y%m%d")
        df.set_index("영업일자", inplace=True)

        # ✅ 숫자형 변환 시도
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
    


    def get_short_sale_daily_trend_df_multi(self, symbol, start_date, end_date, market_code="J") -> pd.DataFrame:
        """
        start_date ~ end_date 전체 구간을 공매도 API 제한을 고려해 여러 번 나눠 호출하여 모두 연결
        
        Returns:
            pd.DataFrame: 전체 날짜 구간의 공매도 df (index = datetime)
        """

        all_data = []

        # 한 번에 조회 가능한 최대 기간 (약 90일, 여유 있게 85일로 제한)
        chunk_days = 85
        current_start = start_date

        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=chunk_days - 1), end_date)

            try:
                df = self.get_short_sale_daily_trend(
                    symbol=symbol,
                    start_date=current_start.strftime("%Y%m%d"),
                    end_date=current_end.strftime("%Y%m%d"),
                    market_code=market_code
                )
                if df is not None and not df.empty:
                    all_data.append(df)

            except Exception as e:
                print(f"⚠️ 공매도 데이터 요청 실패: {current_start} ~ {current_end}: {e}")

            current_start = current_end + timedelta(days=1)

        if all_data:
            full_df = pd.concat(all_data).sort_index()
            # 중복 제거 (혹시 API가 중복 포함할 수 있으므로)
            full_df = full_df[~full_df.index.duplicated(keep='last')]
            return full_df

        print(f"❌ 전체 구간에 대해 공매도 데이터 없음: {symbol}")
        return pd.DataFrame()
    