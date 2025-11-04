import time
import numpy as np
import pandas as pd
import requests
import math
import matplotlib.pyplot as plt
from pykis import PyKis, KisChart, KisStock, KisAuth
from datetime import datetime
import mplfinance as mpf
from dotenv import load_dotenv
import os
import json
from pykis import KisQuote
from pykis import KisBalance
from pykis import KisOrder
from pykis import KisRealtimePrice, KisSubscriptionEventArgs, KisWebsocketClient, PyKis
from pykis import PyKis, KisTradingHours
from pykis import PyKis, KisOrderProfits
from pykis import KisRealtimeExecution, KisSubscriptionEventArgs, KisWebsocketClient
import asyncio
from typing import List, Dict
from sqlalchemy.orm import Session
from app.utils.crud_sql import SQLExecutor
from app.utils.database import get_db_session
from app.utils.technical_indicator import TechnicalIndicator



# .env 파일 로드
load_dotenv()



class AutoTradingStock:
    def __init__(self, id, account, real_appkey, real_secretkey, virtual=False, virtual_id=None, virtual_appkey=None, virtual_secretkey=None):
        """
        AutoTradingStock 클래스 초기화
        실전투자와 모의투자를 선택적으로 설정 가능
        """
        # 속성 초기화
        self.virtual = virtual
        self.id = id
        self.account = account  # 계좌 번호 저장
        self.appkey = real_appkey
        self.secretkey = real_secretkey
        self.virtual_id = virtual_id
        self.virtual_appkey = virtual_appkey
        self.virtual_secretkey = virtual_secretkey
        self.ticket = None  # 실시간 체결 구독 티켓
        self.kis = None  # kis 초기화
        self.sql_executor = SQLExecutor()
        
        if self.virtual:
            # 모의투자용 PyKis 객체 생성
            if not all([id,account, real_appkey, real_secretkey,virtual_id, virtual_appkey, virtual_secretkey]):
                raise ValueError("모의투자 정보를 완전히 제공해야 합니다.")
            
            message = ("모의투자 API 객체를 생성 중입니다...")
            self.send_discord_webhook(message,"trading")
            self.kis = PyKis(
                id=id,
                account=account,
                appkey=real_appkey,
                secretkey=real_secretkey,
                virtual_id=virtual_id,
                virtual_appkey=virtual_appkey,
                virtual_secretkey=virtual_secretkey,
                keep_token=True  # API 접속 토큰 자동 저장
            )
            
        else:
            # 실전투자용 PyKis 객체 생성
            message = ("실전투자 API 객체를 생성 중입니다...")
            self.send_discord_webhook(message,"trading")
            self.kis = PyKis(
                id=id,
                account=account,
                appkey=real_appkey,
                secretkey=real_secretkey,
                keep_token=True  # API 접속 토큰 자동 저장
            )
            

        print(f"{'모의투자' if self.virtual else '실전투자'} API 객체가 성공적으로 생성되었습니다.")

        
    def get_account_info(self):
        """투자 유형 및 계좌 정보를 반환"""
        account_type = "모의 투자" if self.virtual else "실전 투자"
        return {
            "투자 유형": account_type,
            "계좌 번호": self.account,
            "사용된 ID": self.virtual_id if self.virtual else self.id

        }

    def send_account_info_to_discord(self):
        """계좌 정보를 디스코드 웹훅에 전송"""
        account_info = self.get_account_info()

        # 정보를 문자열로 정리
        message = (
            "📢 투자 계좌 정보:\n" +
            "\n".join([f"{key}: {value}" for key, value in account_info.items()])
        )
        # 디스코드로 전송
        self.send_discord_webhook(message, "trading")

    def send_discord_webhook(self, message, bot_type):
        if bot_type == 'trading':
            webhook_url = os.getenv('TEST_DISCORD_WEBHOOK_URL')  # 복사한 Discord 웹훅 URL로 변경
            username = "FSTS trading Bot"
            
        elif bot_type == "simulation":
            webhook_url = os.getenv('TEST_DISCORD_SIMULATION_WEBHOOK_URL')  # 복사한 Discord 웹훅 URL로 변경
            username = "FSTS simulation Bot"

        data = {
            "content": message,
            "username": username,  # 원하는 이름으로 설정 가능
        }
        

        # 요청 보내기
        response = requests.post(webhook_url, json=data)
        
        # 응답 확인
        if response.status_code == 204:
            print("메시지가 성공적으로 전송되었습니다.")
        else:
            print(f"메시지 전송 실패: {response.status_code}, {response.text}")


    def get_stock_quote(self, symbol):
        """주식 시세를 가져와 디스코드로 전달"""
        try:
            # 종목 객체 가져오기
            stock = self.kis.stock(symbol)

            # 시세 가져오기
            quote: KisQuote = stock.quote()
            quote: KisQuote = stock.quote(extended=True) # 주간거래 시세
        # 시세 정보 문자열 생성
            message = (
    f"📊 종목 시세 정보\n"
    f"종목 코드: {quote.symbol}\n"
    f"종목명: {quote.name}\n"
    f"업종: {quote.sector_name}\n"
    f"현재가: {quote.close:,.0f} KRW\n"
    f"시가: {quote.open:,.0f} KRW\n"
    f"고가: {quote.high:,.0f} KRW\n"
    f"저가: {quote.low:,.0f} KRW\n"
    f"전일 대비 가격: {quote.change:,.0f} KRW\n"
    f"등락률: {quote.change / (quote.close - quote.change):.2%}\n"
    f"거래량: {quote.volume:,.0f} 주\n"
    f"거래 대금: {quote.amount:,} KRW\n"
    f"시가총액: {quote.market_cap:,} 억 KRW\n"
    f"52주 최고가: {quote.indicator.week52_high:,.0f} KRW (일자: {quote.indicator.week52_high_date})\n"
    f"52주 최저가: {quote.indicator.week52_low:,.0f} KRW (일자: {quote.indicator.week52_low_date})\n"
    f"EPS (주당순이익): {quote.indicator.eps:,.0f} KRW\n"
    f"BPS (주당순자산): {quote.indicator.bps:,.0f} KRW\n"
    f"PER (주가수익비율): {quote.indicator.per}\n"
    f"PBR (주가순자산비율): {quote.indicator.pbr}\n"
    f"단위: {quote.unit}\n"
    f"호가 단위: {quote.tick:,.0f} KRW\n"
    f"거래 정지 여부: {'정지' if quote.halt else '정상'}\n"
    f"과매수 상태: {'예' if quote.overbought else '아니오'}\n"
    f"위험도: {quote.risk.capitalize()}\n"
    )
            # 디스코드 웹훅 전송
            self.send_discord_webhook(message,"simulation")

            # 디버깅용 출력
            print("주식 시세 정보:", message)
        except Exception as e:
            print(f"주식 시세 조회 중 오류 발생: {e}")
            error_message = f"❌ 주식 시세 조회 중 오류 발생: {e}"
            self.send_discord_webhook(error_message,"simulation")
            
    def inquire_balance(self):
        """잔고 정보를 디스코드 웹훅으로 전송"""
        
                # 주 계좌 객체를 가져옵니다.
        account = self.kis.account()

        balance: KisBalance = account.balance()

        print(repr(balance)) # repr을 통해 객체의 주요 내용을 확인할 수 있습니다.
        
        try:
            # 기본 잔고 정보
            message = (
                f"📃 주식 잔고 정보\n"
                f"계좌 번호: {balance.account_number}\n"
                f"총 구매 금액: {balance.purchase_amount:,.0f} KRW\n"
                f"현재 평가 금액: {balance.current_amount:,.0f} KRW\n"
                f"총 평가 손익: {balance.profit:,.0f} KRW\n"
                f"총 수익률: {balance.profit_rate/ 100:.2%}\n\n"
            )
            
            
            # 보유 종목 정보 추가
            message += "📊 보유 종목 정보:\n"
            for stock in balance.stocks:
                message += (
                    f"종목명: {stock.symbol} (시장: {stock.market})\n"
                    f"수량: {stock.qty:,}주\n"
                    f"평균 단가: {stock.price:,.0f} KRW\n"
                    f"평가 금액: {stock.amount:,.0f} KRW\n"
                    f"평가 손익: {stock.profit:,.0f} KRW\n"
                    f"수익률: {stock.profit_rate /100:.2%}\n\n"
                )
                
                
            # 예수금 정보 추가
            message += "💰 예수금 정보:\n"
            for currency, deposit in balance.deposits.items():
                message += (
                    f"통화: {currency}\n"
                    f"금액: {deposit.amount:,.0f} {currency}\n"
                    f"환율: {deposit.exchange_rate}\n\n"
                )

            # 디스코드 웹훅으로 메시지 전송
            self.send_discord_webhook(message, "trading")

        except Exception as e:
            # 오류 메시지 처리
            error_message = f"❌ 잔고 정보를 처리하는 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")
    
    
    def place_order(self, symbol, qty, buy_price=None, sell_price=None, order_type="buy"):
        """주식 매수/매도 주문 함수
        Args:
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
                message = f"📈 매수 주문 완료! 종목: {symbol}, 수량: {qty}, 가격: {'시장가' if not buy_price else buy_price}"
            elif order_type == "sell":
                if sell_price:
                    order = stock.sell(price=sell_price)  # 지정가 매도
                else:
                    order = stock.sell()  # 시장가 매도
                message = f"📉 매도 주문 완료! 종목: {symbol}, 수량: {qty}, 가격: {'시장가' if not sell_price else sell_price}"
            else:
                raise ValueError("Invalid order_type. Must be 'buy' or 'sell'.")

            # 디스코드로 주문 결과 전송
            self.send_discord_webhook(message, "trading")

            return order

        except Exception as e:
            error_message = f"주문 처리 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")

    
    def get_trading_hours(self, country_code):
        """
        특정 국가의 주식 시장 거래 시간을 조회합니다.
        Args:
            country_code (str): 국가 코드 (예: US, KR, JP)
        """
        try:
            # 거래 시간 조회
            trading_hours: KisTradingHours = self.kis.trading_hours(country_code)

            # 메시지 정리
            message = (
                f"📅 **{country_code} 주식 시장 거래 시간**\n"
                f"정규 거래 시작: {trading_hours.open_kst}\n"
                f"정규 거래 종료: {trading_hours.close_kst}\n"
            )

            # 결과 출력 및 웹훅 전송
            print(message)
            self.send_discord_webhook(message, "trading")
            return message
        
        except Exception as e:
            error_message = f"❌ 거래 시간 조회 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")
            return None

    def get_investor_trend(self, market_code="KSP", industry_code="0001"):
        """
        시장별 투자자 매매동향을 조회합니다.
        Args:
            market_code (str): 시장 코드 (KSP: KOSPI, KSQ: KOSDAQ)
            industry_code (str): 업종 코드
        Returns:
            dict: 조회 결과
        """
        
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market"
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            'Authorization': str(self.kis.token),
            "appkey": self.appkey,
            "appsecret": self.secretkey,
            "tr_id": "FHPTJ04030000",
            "custtype" :"P" # 실전 거래용 TR_ID
        }
        
        params = {
            "fid_input_iscd": market_code,  # 시장 코드
            "fid_input_iscd_2": industry_code,  # 업종 코드
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                result = response.json()
                output = result.get("output", [])

                # 결과 메시지 생성
                if not output:  # output이 비어있을 경우 처리
                    self.send_discord_webhook("❌ 조회된 투자자 매매동향 데이터가 없습니다.", "trading")
                else:
                    # output은 단일 리스트로 가정
                    item = output[0]  # 리스트 내 첫 번째 항목 처리
                    message = (
                        f"**📊 {market_code} 투자자 매매동향 결과**\n"
                        f"외국인 매도 거래 대금: {item['frgn_seln_tr_pbmn']}\n"
                        f"외국인 매수 거래 대금: {item['frgn_shnu_tr_pbmn']}\n"
                        f"외국인 순매수 거래 대금: {item['frgn_ntby_tr_pbmn']}\n\n"
                        f"기관 매도 거래 대금: {item['orgn_seln_tr_pbmn']}\n"
                        f"기관 매수 거래 대금: {item['orgn_shnu_tr_pbmn']}\n"
                        f"기관 순매수 거래 대금: {item['orgn_ntby_tr_pbmn']}\n\n"
                        f"개인 매도 거래 대금: {item['prsn_seln_tr_pbmn']}\n"
                        f"개인 매수 거래 대금: {item['prsn_shnu_tr_pbmn']}\n"
                        f"개인 순매수 거래 대금: {item['prsn_ntby_tr_pbmn']}\n"
                    )
                    self.send_discord_webhook(message, "trading")
            else:
                error_message = f"❌ API 호출 실패: {response.status_code}, {response.text}"
                self.send_discord_webhook(error_message, "trading")
        except Exception as e:
            error_message = f"❌ 투자자매매동향 조회 중 오류 발생: {e}"
            self.send_discord_webhook(error_message,"trading")


# #직접 API 호출한 체결강도 순위 조회
#     def get_volume_power_ranking(self, market_code="J", input_market="2001"):
#         """
#         시장별 거래량 순위 조회 메소드
#         Args:
#         market_code (str): 시장 코드 (KOSPI: "J", KOSDAQ: "Q", 전체: "U")
#         """
#         # API 요청 URL
#         url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/volume-power"

#         # 요청 헤더 설정
#         headers = {
#             "Content-Type": "application/json; charset=utf-8",
#             "Authorization": str(self.kis.token),
#             "appkey": self.appkey,
#             "appsecret": self.secretkey,
#             "tr_id": "FHPST01680000",
#             "custtype": "P"
#         }

#         # 요청 파라미터 설정
#         params = {
#             "fid_trgt_exls_cls_code": "0",
#             "fid_cond_mrkt_div_code": market_code,
#             "fid_cond_scr_div_code": "20168",
#             "fid_input_iscd": input_market,
#             "fid_div_cls_code": "0",
#             "fid_input_price_1": "",
#             "fid_input_price_2": "",
#             "fid_vol_cnt": "",
#             "fid_trgt_cls_code": "0"
#         }

#         try:
#             # API 요청
#             response = requests.get(url, headers=headers, params=params)

#             if response.status_code == 200:
#                 result = response.json()
#                 rankings = result.get("output", [])
                
#                 # 조회된 결과를 문자열로 정리
#                 message = "**📊 체결강도 순위 조회 결과:**\n"
#                 for idx, stock in enumerate(rankings[:10]):  # 상위 10개 종목만 표시
#                     message += (
#                         f"{idx+1}. 종목명: {stock['hts_kor_isnm']}\n"
#                         f"종목코드: {stock["stck_shrn_iscd"]}\n"
#                         f"당일 체결강도: {stock['tday_rltv']}\n"
                        
#                     )
#                 print(message)
#                 self.send_discord_webhook(message, "trading")

#             else:
#                 error_message = f"❌ 거래량 순위 조회 실패: {response.status_code} {response.text}"
#                 print(error_message)
#                 self.send_discord_webhook(error_message, "trading")

#         except Exception as e:
#             error_message = f"❌ 거래량 순위 조회 중 오류 발생: {e}"
#             print(error_message)
#             self.send_discord_webhook(error_message, "trading")

#매도 과정은 빼기?
    def get_volume_power_ranking_and_trade(self, input_market="2001"):
        """
        체결강도 순위를 조회하고 조건에 따라 종목을 자동으로 매수/매도
        Args:
            market_code (str): 시장 코드 (KOSPI: "J", KOSDAQ: "Q", 전체: "U")
            input_market (str): 조회할 시장 코드
        """
        # API 요청 URL
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/volume-power"

        # 요청 헤더 설정
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": str(self.kis.token),
            "appkey": self.appkey,
            "appsecret": self.secretkey,
            "tr_id": "FHPST01680000",
            "custtype": "P"
        }

        # 요청 파라미터 설정
        params = {
            "fid_trgt_exls_cls_code": "0",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20168",
            "fid_input_iscd": input_market,
            "fid_div_cls_code": "0",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0"
        }

        try:
            # API 요청 보내기
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                result = response.json()
                rankings = result.get("output", [])

                # 메시지 구성
                message = "**📊 체결강도 상위 종목 조회 및 자동 매수/매도**\n"
                top_stocks = []

                for idx, stock in enumerate(rankings[:5]):  # 상위 5개 종목만 처리
                    stock_name = stock['hts_kor_isnm']
                    stock_code = stock['stck_shrn_iscd']
                    volume_power = float(stock['tday_rltv'])

                    message += (
                        f"{idx+1}. 종목명: {stock_name}\n"
                        f"종목코드: {stock_code}\n"
                        f"체결강도: {volume_power:.2f}\n"
                    )

                # 결과를 디스코드에 전송
                print(message)
                self.send_discord_webhook(message, "trading")


                # 체결강도 1위 종목 선택
                top_stock = rankings[0]
                stock_name = top_stock['hts_kor_isnm']
                stock_code = top_stock['stck_shrn_iscd']
                volume_power = float(top_stock['tday_rltv'])
                


                # 1주 매수 실행 (시장가)
                buy_qty = 1
                buy_price = None  # 시장가
                order_result = self.place_order(stock_code, buy_qty, buy_price, order_type="buy")

                if order_result:
                    self.send_discord_webhook(
                        f"✅ 매수 완료: 종목명: {stock_name}, 수량: {buy_qty}주, 가격: 시장가\n", "trading" 
                    )
                    
                    print(f"✅ 매수 완료: {stock_name} - 수량: {buy_qty}주")

                    # 매수 가격 저장
                    stock = self.kis.stock(stock_code)
                    quote = stock.quote()
                    purchase_price = float(quote.close)  # 매수가격 설정

                    # 5% 상승 시 매도 조건 확인
                    sell_price = round(purchase_price*1.05, 2)  # 매수가 대비 5% 상승
                    self.monitor_and_sell(stock_code, stock_name, buy_qty, purchase_price, sell_price)
                else:
                    self.send_discord_webhook(f"❌ 매수 실패: 종목명: {stock_name}", "trading")
            else:
                error_message = f"❌ 체결강도 조회 실패: {response.status_code}, {response.text}"
                print(error_message)
                self.send_discord_webhook(error_message, "trading")

        except Exception as e:
            error_message = f"❌ 체결강도 조회 및 자동매수 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")


    async def monitor_and_sell(self, stock_code, stock_name, qty, purchase_price, sell_price, timeout=1800, interval = 60):
        """
        매수가 대비 5% 상승 시 자동 매도
        """
        try:
            stock = self.kis.stock(stock_code)
            start_time = time.time()

            while True:
                # 현재 시간과 시작 시간 비교
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    self.send_discord_webhook(
                        f"⏳ 매도 조건 시간이 초과되었습니다. 목표가: {sell_price}원", "trading"
                    )
                    print("⏳ 매도 조건 시간이 초과되었습니다.")
                    break

                # 현재가 조회
                quote = stock.quote()
                current_price = float(quote.close)

                print(f"[{elapsed_time:.0f}초 경과] 현재가: {current_price}, 목표 매도가: {sell_price}")

                # 목표가 도달 시 매도 실행
                if current_price >= sell_price:
                    order_result = self.place_order(stock_code, qty, sell_price, order_type="sell")

                    if order_result:
                        profit = current_price - purchase_price
                        profit_rate = (profit / purchase_price) * 100

                        message = (
                            f"✅ 자동 매도 완료!\n"
                            f"종목명: {stock_name}\n"
                            f"매수가: {purchase_price}원\n"
                            f"매도가: {current_price}원\n"
                            f"수익률: {profit_rate:.2f}%"
                        )
                        print(message)
                        self.send_discord_webhook(message, "trading")
                    else:
                        self.send_discord_webhook(
                            f"❌ 매도 실패: 종목명: {stock_name}", "trading"
                        )
                    break

                # 일정 시간 대기
                await asyncio.sleep(interval)

        except Exception as e:
            error_message = f"❌ 매도 조건 확인 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")

    # 배당률 상위 조회 함수
    def get_top_dividend_stocks(self,db: Session):
        # 실전 투자 환경 URL
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/dividend-rate"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            'Authorization': str(self.kis.token),
            "appkey": self.appkey,
            "appsecret": self.secretkey,
            "tr_id": "HHKDB13470100",  # 실전 거래용 TR_ID
            "custtype": "P"
        }

        # 요청 쿼리 파라미터 설정
        params = {
            "CTS_AREA": "",
            "GB1": "0",  # 전체 조회 #0:전체, 1:코스피, 2: 코스피200, 3: 코스닥
            "UPJONG": "0001",  # 업종 코드 (예시) 코스피(0001:종합) 코스닥(1001:종합)
            "GB2": "6",  # 배당률 순서
            'GB3': '2',
            "F_DT": "20230101",  # 시작 날짜
            "T_DT": "20241201",  # 종료 날짜
            "GB4": "0"  # 기타 설정
        }

        # API 요청 보내기
        response = requests.get(url, headers=headers, params=params)

        # 응답 처리
        if response.status_code == 200:
            result = response.json()
            # 상위 5개 항목 추출
            top_stocks = result.get("output", [])[:5]

            # 결과 정리
            message = "📊 KOSPI 배당률 상위 5:\n"
            for idx, stock in enumerate(top_stocks):
                dividend_rate = float(stock['divi_rate']) / 100
                
                message +=(
                    f"{idx+1}. 종목명: {stock['isin_name']}\n"
                    f"날짜: {stock['record_date']}\n"
                    f"현금/주식배당금: {stock["per_sto_divi_amt"]}\n"
                    f"배당률: {dividend_rate:.2f}% \n"
                )
            
        
            # 디스코드 웹훅 전송
            self.send_discord_webhook(message, "trading")
                    
            # DB에 데이터 삽입
            for stock in top_stocks:
                query = """
                    INSERT INTO fsts.dividend_stocks (isin_name, record_date, per_sto_divi_amt, dividend_rate)
                    VALUES (:isin_name, :record_date, :per_sto_divi_amt, :dividend_rate)
                    RETURNING *
                """
                params = {
                    "isin_name": stock['isin_name'],
                    "record_date": stock['record_date'],
                    "per_sto_divi_amt": float(stock['per_sto_divi_amt']),
                    "dividend_rate": float(stock['divi_rate']) / 100
                }
                self.sql_executor.execute_insert(db, query, params)

            print("📊 배당률 상위 5종목이 DB에 저장되었습니다.")
            
        else:
            error_message = f"❌ 배당률 조회 실패: {response.status_code}, {response.text}"
            self.send_discord_webhook(error_message, "trading")
            print(error_message)


    def get_income_statement(self, symbol: str):
        """
        국내주식 손익계산서를 가져와 디스코드로 전송하는 함수
        Args:
            symbol (str): 종목 코드
        """
        
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/finance/income-statement"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": str(self.kis.token),
            "appkey": self.appkey,
            "appsecret": self.secretkey,
            "tr_id": "FHKST66430200",  # 실전 투자용 TR_ID
            "custtype": "P"
        }
        params = {
            "FID_DIV_CLS_CODE": "0",  # 0: 연도별 데이터, 1: 분기별 데이터
            "fid_cond_mrkt_div_code": "J",  # 시장 코드
            "fid_input_iscd": symbol  # 종목 코드
        }

        try:
            # API 호출
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            result = response.json()

            # API 실패 처리
            if result.get("rt_cd") != "0":
                error_message = f"⚠️ API 오류: {result.get('msg1')}"
                self.send_discord_webhook(error_message, "trading")
                return

            # 데이터 가져오기
            income_data = result.get("output", [])
            if not income_data:
                self.send_discord_webhook(f"⚠️ {symbol}에 대한 손익계산서 데이터가 없습니다.", "trading")
                return

            # 최근 2년 데이터 필터링
            current_year = datetime.now().year
            recent_data = [
                data for data in income_data if int(data["stac_yymm"][:4]) >= current_year - 2
            ]

            if not recent_data:
                self.send_discord_webhook(f"⚠️ 최근 2년간 손익계산서 데이터가 없습니다.", "trading")
                return

            # 메시지 생성
            message = f"📊 {symbol} 최근 3년간 손익계산서:\n"
            for data in recent_data:
                message += (
                    f"결산 년월: {data['stac_yymm']}\n"
                    f"매출액: {data['sale_account']} KRW\n"
                    f"매출 원가: {data['sale_cost']} KRW\n"
                    f"매출 총이익: {data['sale_totl_prfi']} KRW\n"
                    f"영업 이익: {data['bsop_prti']} KRW\n"
                    f"당기순이익: {data['thtr_ntin']} KRW\n"
                    f"-----------------------------\n"
                )

            # 디스코드에 메시지 전송
            self.send_discord_webhook(message, "trading")

        except requests.exceptions.RequestException as req_err:
            error_message = f"❌ API 호출 중 오류 발생: {req_err}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")

        except Exception as e:
            # 일반적인 예외 처리
            error_message = f"❌ 손익계산서 조회 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "trading")
            
    def fetch_foreign_investor_data(self, symbol: str, start_date: str, end_date: str) -> list:
        """
        외국인 순매수 데이터를 가져옵니다.
        Args:
            symbol (str): 종목 코드
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
        Returns:
            list: 특정 기간에 해당하는 외국인 순매수 데이터 리스트
        """
        
        try:
            print(f"[INFO] 외국인 순매수 데이터 가져오기 시작... 종목: {symbol}, 기간: {start_date} ~ {end_date}")

            # API 요청 URL
            url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor"

            # API 요청 헤더
            headers = {
                "authorization": str(self.kis.token),
                "appkey": self.appkey,
                "appsecret": self.secretkey,
                "tr_id": "FHKST01010900",  # 실전 거래용 TR_ID
            }

            # API 요청 파라미터
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # 시장 코드 (KOSPI)
                "FID_INPUT_ISCD": symbol,  # 종목 코드
            }

            # API 요청
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            # 응답 데이터 파싱
            result = response.json()

            if result.get("rt_cd") != "0":
                print(f"[WARNING] API 호출 실패: {result.get('msg1')}")
                self.send_discord_webhook(f"⚠️ API 호출 실패: {result.get('msg1')}", "simulation")
                return []

            all_data = result.get("output", [])
            if not all_data:
                print(f"[INFO] {symbol}에 대한 데이터가 없습니다.")
                return []

            # 데이터 필터링: 사용자 지정 날짜에 맞는 데이터만 반환
            filtered_data = []
            for entry in all_data:
                entry_date = entry["stck_bsop_date"]
                print(f"[DEBUG] 반환된 데이터 날짜: {entry_date}")  # 반환된 날짜 확인

                if start_date <= entry_date <= end_date:
                    filtered_data.append({
                        "symbol": symbol,
                        "date": entry_date,  # 날짜
                        "foreign_net_buy": float(entry["frgn_ntby_tr_pbmn"]),  # 외국인 순매수 거래 대금
                        "close_price": float(entry["stck_clpr"]),  # 종가
                    })

            print(f"[INFO] 데이터 변환 완료! 총 {len(filtered_data)}개의 데이터가 준비되었습니다.")
            return filtered_data

        except Exception as e:
            print(f"[ERROR] 외국인 순매수 데이터 가져오는 중 오류 발생: {e}")
            self.send_discord_webhook(f"❌ 외국인 순매수 데이터 가져오는 중 오류 발생: {e}", "simulation")
            return []
        
    # 봉 데이터를 가져오는 함수
    def _get_ohlc(self, symbol, start_date, end_date, mode="default"):
        symbol_stock: KisStock = self.kis.stock(symbol)  # SK하이닉스 (코스피)
        chart: KisChart = symbol_stock.chart(
            start=start_date,
            end=end_date,
        ) # 2023년 1월 1일부터 2023년 12월 31일까지의 일봉입니다.
        klines = chart.bars

        # 첫 번째 데이터를 제외하고, 각 항목의 open 값을 전날 close 값으로 변경 
        # mode = continuous
        if mode == 'continuous':
            for i in range(1, len(klines)):
                klines[i].open = klines[i - 1].close  # 전날의 close로 open 값을 변경
            
        return klines
        
    def rsi_simulate_trading(self, symbol: str, start_date: str, end_date: str, 
                    rsi_window: int = 14, buy_threshold: int = 50, sell_threshold: int = 70):
        """
        RSI 매매 로직 및 시각화 데이터 포함
        Args:
            symbol (str): 종목 코드
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
            rsi_window (int): RSI 계산에 사용할 기간
            buy_threshold (float): RSI 매수 임계값
            sell_threshold (float): RSI 매도 임계값
        """
        # 문자열 날짜를 datetime.date 타입으로 변환
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        print(f"[DEBUG] RSI 매매 시작 - 종목: {symbol}, 기간: {start_date} ~ {end_date}")
        
        # OHLC 데이터 조회
        ohlc_data = self._get_ohlc(symbol, start_date, end_date)

        # 초기화
        realized_pnl = 0  # 총 실현 손익
        position = 0  # 현재 포지션
        current_cash = 1_000_000  # 초기 자본
        buy_signals = []  # 매수 신호
        sell_signals = []  # 매도 신호

        # 그래프 데이터 저장용
        timestamps = []
        ohlc = []
        closes = []

        for candle in ohlc_data:
            open_price = float(candle.open)
            high_price = float(candle.high)
            low_price = float(candle.low)
            close_price = float(candle.close)
            timestamp = candle.time

            # OHLC 데이터 수집
            timestamps.append(timestamp)
            ohlc.append([open_price, high_price, low_price, close_price])
            closes.append(close_price)

        print(f"[DEBUG] 가져온 종가 데이터: {closes[:20]}... (총 {len(closes)} 개)")
        
        technical_indicator = TechnicalIndicator()
        
        # RSI 계산
        rsi_values = technical_indicator.calculate_rsi(closes, rsi_window)
        print(f"[DEBUG] 계산된 RSI 데이터: {rsi_values[:20]}... (총 {len(rsi_values)} 개)")

        for i in range(rsi_window, len(rsi_values)):
            close_price = closes[i]
            rsi = rsi_values[i]
            prev_rsi = rsi_values[i - 1]
            date = timestamps[i]

            # 디버깅 로그
            print(f"[DEBUG] 날짜: {date}, 종가: {close_price:.2f}, RSI: {rsi}, 이전 RSI: {prev_rsi}")

            # **RSI 값이 None인 경우 건너뜀**
            if rsi is None or prev_rsi is None:
                print("[DEBUG] RSI 값이 None입니다. 루프를 건너뜁니다.")
                continue

            # 매수 조건: RSI가 buy_threshold를 상향 돌파
            if rsi > buy_threshold and prev_rsi < buy_threshold and current_cash >= close_price:
                position += 1
                current_cash -= close_price
                buy_signals.append((date, close_price))
                print(f"[DEBUG] 📈 매수 발생! 날짜: {date}, 가격: {close_price:.2f}, RSI: {rsi}")
                self.send_discord_webhook(
                    f"📈 매수 발생! 종목: {symbol}, 가격: {close_price}, RSI: {rsi:.2f}, 이전 RSI: {prev_rsi:.2f}, 시간: {date}",
                    "simulation"
                )

            # 매도 조건: RSI가 sell_threshold를 상향 돌파 후 다시 하락
            elif rsi < sell_threshold and prev_rsi > sell_threshold and position > 0:
                current_cash += close_price
                pnl = close_price - buy_signals[-1][1]  # 개별 거래 손익
                realized_pnl += pnl
                position -= 1
                sell_signals.append((date, close_price))
                print(f"[DEBUG] 📉 매도 발생! 날짜: {date}, 가격: {close_price:.2f}, RSI: {rsi}, 손익: {pnl:.2f}")
                self.send_discord_webhook(
                    f"📉 매도 발생! 종목: {symbol}, 가격: {close_price}, RSI: {rsi:.2f}, 이전 RSI: {prev_rsi:.2f}, 시간: {date}, 손익: {pnl:.2f} KRW",
                    "simulation"
                )

        # 최종 평가
        final_assets = current_cash + (position * closes[-1] if position > 0 else 0)
        print(f"[DEBUG] 최종 평가 완료 - 최종 자산: {final_assets:.2f}, 총 실현 손익: {realized_pnl:.2f}")
        self.send_discord_webhook(
            f"📊 RSI 매매 시뮬레이션 완료\n"
            f"종목: {symbol}\n"
            f"기간: {start_date} ~ {end_date}\n"
            f"최종 자산: {final_assets} KRW\n"
            f"현금 잔고: {current_cash} KRW\n"
            f"보유 주식 평가 금액: {(position * closes[-1])} KRW\n"
            f"총 실현 손익: {realized_pnl} KRW\n",
            "simulation"
        )

        # 캔들 차트 시각화
        simulation_plot = self.visualize_trades(symbol, ohlc, timestamps, buy_signals, sell_signals)
        return simulation_plot, buy_signals, sell_signals, final_assets, realized_pnl

    def visualize_trades(self, symbol, ohlc, timestamps, buy_signals, sell_signals):
        """
        매수/매도 신호를 포함한 거래 차트를 시각화합니다.
        Args:
            symbol (str): 종목 코드
            ohlc (list): OHLC 데이터 리스트 (각 요소는 [Open, High, Low, Close])
            timestamps (list): 타임스탬프 데이터 리스트
            buy_signals (list): 매수 신호 (각 요소는 (timestamp, price) 형태)
            sell_signals (list): 매도 신호 (각 요소는 (timestamp, price) 형태)
        Returns:
            matplotlib.figure.Figure: 생성된 차트의 Figure 객체
        """

        df = pd.DataFrame(ohlc, columns=["Open", "High", "Low", "Close"], index=pd.DatetimeIndex(timestamps))

        # 매수/매도 신호 열 추가 및 초기화
        df["Buy_Signal"] = pd.Series(index=df.index, dtype="float64")
        df["Sell_Signal"] = pd.Series(index=df.index, dtype="float64")

        for date, price in buy_signals:
            if date in df.index:
                df.at[date, "Buy_Signal"] = price

        for date, price in sell_signals:
            if date in df.index:
                df.at[date, "Sell_Signal"] = price
            
        # NaN 값 제거 또는 대체 (mplfinance에서 오류 방지)
        df["Buy_Signal"].fillna(0, inplace=True)
        df["Sell_Signal"].fillna(0, inplace=True)

        # mplfinance 추가 플롯 설정
        add_plots = [
            mpf.make_addplot(df["Buy_Signal"], type="scatter", markersize=100, marker="^", color="green", label="Buy Signal"),
            mpf.make_addplot(df["Sell_Signal"], type="scatter", markersize=100, marker="v", color="red", label="Sell Signal")
        ]

        # 캔들 차트 플롯 생성
        fig, ax = mpf.plot(
            df,
            type="candle",
            style="charles",
            title=f"{symbol} Trading Signals",
            ylabel="Price (KRW)",
            addplot=add_plots,
            returnfig=True,
            figsize=(20, 10)
        )

        return fig
    
    def foreign_investor_simulate_trading(self, data:list):
        """
        외국인 순매수 데이터를 기반으로 매매 시뮬레이션을 수행합니다.
        Args:
            symbol (str): 종목 코드
            start_date (str): 시작 날짜 (YYYYMMDD 형식)
            end_date (str): 종료 날짜 (YYYYMMDD 형식)
            initial_cash (float): 초기 자본
        """
        try:
            print(f"[INFO] 총 {len(data)}개의 데이터가 준비되었습니다.")
            
            # 초기화
            realized_pnl = 0  # 총 실현 손익
            position = 0  # 현재 보유 주식 수량
            current_cash = 1_000_000  # 초기 자산
            trade_stack = []  # 매수 가격 스택
            recent_foreign_net_buys = []  # 최근 외국인 순매수 상태를 추적
            closes = []  # 종가 데이터

            # 데이터 순회
            for entry in data:
                symbol = entry["symbol"]
                date = entry["date"]
                net_buy = entry["foreign_net_buy"]
                close_price = entry["close_price"]

                closes.append(close_price)
                recent_foreign_net_buys.append(net_buy)
                if len(recent_foreign_net_buys) > 3:
                    recent_foreign_net_buys.pop(0)

                # 매수 조건: 외국인 순매수가 음수 → 양수 전환 + 양수 3일 연속 유지
                buy_signal = (
                    len(recent_foreign_net_buys) == 3
                    and recent_foreign_net_buys[0] < 0  # 첫날 음수
                    and all(val > 0 for val in recent_foreign_net_buys[1:])  # 마지막 2일 양수
                )

                # 매도 조건: 외국인 순매수가 연속 2일 음수로 바뀜
                sell_signal = (
                    position > 0
                    and len(recent_foreign_net_buys) >= 2
                    and all(val < 0 for val in recent_foreign_net_buys[-2:])
                )

                # 3. 매수 작업
                if buy_signal and current_cash >= close_price:
                    position += 1  # 보유 주식 증가
                    trade_stack.append(close_price)  # 매수가 저장
                    current_cash -= close_price  # 현금 잔고 감소

                    self.send_discord_webhook(
                        f"📈 매수 발생! 종목: {symbol}, 날짜: {date}, 가격: {close_price} KRW", "simulation"
                    )
                    print(f"[BUY] 날짜: {date}, 매수가: {close_price} KRW, 현재 잔고: {current_cash} KRW, 보유 주식: {position}")

                # 4. 매도 작업
                if sell_signal:
                    entry_price = trade_stack.pop(0)  # 매수 가격 가져오기
                    pnl = close_price - entry_price  # 개별 거래 손익
                    realized_pnl += pnl  # 총 손익 업데이트
                    current_cash += close_price  # 현금 잔고 증가
                    position -= 1  # 보유 주식 감소

                    self.send_discord_webhook(
                        f"📉 매도 발생! 종목: {symbol}, 날짜: {date}, 매도가: {close_price} KRW, 손익: {pnl:.2f} KRW",
                        "simulation",
                    )
                    print(f"[SELL] 날짜: {date}, 매도가: {close_price} KRW, 손익: {pnl:.2f} KRW, 현재 잔고: {current_cash} KRW, 보유 주식: {position}")

            # 5. 최종 평가
            final_assets = current_cash + (position * closes[-1] if position > 0 else 0)  # 총 자산
            self.send_discord_webhook(
                f"📊 시뮬레이션 완료!\n"
                f"종목: {symbol}\n"
                f"최종 자산: {final_assets:.2f} KRW\n"
                f"현금 잔고: {current_cash:.2f} KRW\n"
                f"보유 주식 평가 금액: {(position * closes[-1]):.2f} KRW\n"
                f"총 실현 손익: {realized_pnl:.2f} KRW\n",
                "simulation"
            )
            
            print(f"[INFO] 시뮬레이션 완료! 최종 자산: {final_assets:.2f} KRW")

        except Exception as e:
            error_message = f"❌ 외국인 순매수 시뮬레이션 중 오류 발생: {e}"
            print(error_message)
            self.send_discord_webhook(error_message, "simulation")
            



            
            



