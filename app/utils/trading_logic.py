from app.utils.technical_indicator import TechnicalIndicator
import pandas as pd
import io
import numpy as np


# 보조지표 클래스 선언
indicator = TechnicalIndicator()
class TradingLogic:

    def __init__(self):
        self.trade_reasons = []

### -------------------------------------------------------------매수로직-------------------------------------------------------------
    def ema_breakout_trading(self, df, symbol):
        """
        공매도 평균단가 상향 돌파 기반 매수 신호 생성 및 사유 기록

        조건:
        - 전일 종가 < 전일 평균가격
        - 당일 종가 >= 당일 평균가격
        """

        if df.shape[0] < 3 or '공매도평균가격' not in df.columns:
            print(f"❌ 데이터 부족 또는 공매도 평균단가 없음: {symbol}")
            return False, None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()

        # 조건 1: 공매도 평균단가 상향 돌파
        breakout_condition = last["Close"] >= last["공매도평균가격"] and last["공매도평균가격"] >= prev['공매도평균가격']
        
        # ✅ 조건 B: 공매도 비중 감소
        short_ratio_drop = '공매도거래량비중' in df.columns and last['공매도거래량비중'] < prev['공매도거래량비중']

        # ✅ 최종 매수 조건
        buy_signal = breakout_condition

        return buy_signal, None
    
    def ema_breakout_trading2(self, df, symbol):
        """
        황금비로 지수이동평균 계산

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: 거래대금 계산(30억 이상)
        trade_value = close_price * volume

        # 조건 2: EMA_10이 EMA_20 상향 돌파
        cross_up = (
            prev['EMA_13'] <= prev['EMA_21'] and
            last['EMA_13'] > last['EMA_21']
        )

        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_13'] - prev['EMA_13']
        ema20_slope = last['EMA_21'] - prev['EMA_21']
        ema50_slope = last['EMA_55'] - prev['EMA_55']
        ema60_slope = last['EMA_89'] - prev['EMA_89']
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0

        # 조건 4: 거래량 증가
        volume_up = last['Volume'] > last['Volume_MA5']
        volume_up2 = last['Volume'] > prev['Volume']
        
        # ❌ 조건 5: 당일 윗꼬리 음봉 제외, 윗꼬리 조건 추가
        is_bearish = last['Close'] > last['Open']
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
    
        # 최종 조건
        buy_signal = cross_up and slope_up and volume_up and is_bearish and volume_up2 and not_long_upper_shadow

        return buy_signal, None
    
    def bottom_rebound_trading(self, df):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """
        buy_yn1, _ = self.trend_entry_trading(df)
        buy_yn2, _ = self.ema_crossover_trading(df)
        buy_yn3, _ = self.should_buy_break_high_trend(df)
    
        buy_signal = buy_yn1 and buy_yn2 and buy_yn3
        return buy_signal, None
    
    def sma_breakout_trading(self, df, symbol, resistance):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """
        buy_yn1, _ = self.ema_breakout_trading(df, symbol)
        buy_yn2, _ = self.ema_crossover_trading(df, resistance)
    
        buy_signal = buy_yn1 and buy_yn2
        return buy_signal, None
    
    def ema_breakout_trading3(self, df):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None
        
        # if high_trendline is None:
        #     return False, None

        df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: 거래대금 계산(30억 이상)
        trade_value = close_price * volume

        # 조건 2: EMA_5이 EMA_20 상향 돌파
        cross_up = (
            prev['EMA_13'] < prev['EMA_21'] and
            last['EMA_13'] > last['EMA_21'] and
            last['EMA_5'] > last['EMA_13'] > last['EMA_21']
        )

        
        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_13'] - prev['EMA_13']
        ema20_slope = last['EMA_21'] - prev['EMA_21']
        ema50_slope = last['EMA_55'] - prev['EMA_55']
        ema60_slope = last['EMA_89'] - prev['EMA_89']
        
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0
        
            # ✅ 조건 3-1: EMA_50, EMA_60 기울기 평균도 양수여야 함
        slope_ma_up = (
            last['EMA_55_Slope_MA'] > 0
            and last['EMA_89_Slope_MA'] > 0
        )

        # 조건 4: 거래량 증가
        volume_up = last['Volume'] > last['Volume_MA5']
        volume_up2 = last['Volume'] > prev['Volume']
        
        # ❌ 조건 5: 당일 윗꼬리 음봉 제외, 윗꼬리 조건 강화
        is_bearish = last['Close'] < last['Open']
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.8  # 윗꼬리 20% 이상이면 제외
        
        #조건 6
        prev_high_up = last['Close'] >= prev['High']
        
        
        # ✅ 조건 7: 최근 20일 내 고점 돌파
        recent_20_high = df['High'].iloc[-20:].max()
        close_breaks_recent_high = last['Close'] > recent_20_high
        


        # cond1 = prev['Close'] < high_trendline  # 하락추세선 아래 → 상향 돌파
        # cond2 = last['Close'] > high_trendline
        # cond3 = last['Close'] > last_resistance  # 수평 고점도 돌파
        
        
        # 최종 조건
        #buy_signal = cross_up and slope_up and not_long_upper_shadow and slope_ma_up and not is_bearish and volume_up and prev_high_up
        buy_signal = all([cross_up, slope_up, not_long_upper_shadow, slope_ma_up, not is_bearish, volume_up, prev_high_up]) 
        
        print(f"EMA_55_Slope_MA: {last['EMA_55_Slope_MA']}")
        print(f"EMA_89_Slope_MA: {last['EMA_89_Slope_MA']}")

        return buy_signal, None
    
    def ema_crossover_trading(self, df, last_resistance, version=1):
        if len(df) < 2:
            return False, None

        # if last_resistance is None:
        #     return False, None
        
        # 추가
        df["close_minus_ema60"] = df["Close"] - df["EMA_60"]
        df["min_15d_close_minus_ema60"] = (
            df["close_minus_ema60"].rolling(window=15).min()
        )
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        # ✅ 중장기 정배열 조건
        long_trend = (
            last['EMA_10'] > last['EMA_20'] > last['EMA_60'] > last['EMA_120'] 
        )


        # ✅ EMA_5가 전일 EMA_13 아래에 있다가 당일 상향 돌파
        crossover = prev['Close'] <= prev['EMA_5'] and last['Close'] > last['EMA_5']

        # ✅ 종가가 EMA_5, EMA_13 위에 있어야 신뢰도 ↑
        price_above = last['Close'] > last['EMA_5'] and last['Close'] > last['EMA_10']

        # ✅ 거래량 조건 (5일 평균 이상 & 전일보다 증가)
        volume_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
        volume_good = last['Volume'] > volume_ma5 and last['Volume'] > prev['Volume']

        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        cond5  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
        cond6 = last['Close'] > last["Open"]
        
        cond7 = prev_prev['Close'] >= prev_prev['EMA_5'] and prev['Close'] <= prev['EMA_5'] and last['Close'] > last['EMA_5']
        
                # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        ema120_slope = last['EMA_120'] - prev['EMA_120']
        
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema60_slope > 0 and ema120_slope > 0
        
        bollinger_upper_slope = last['BB_Upper'] - prev['BB_Upper']
        bollinger_lower_slope = last['BB_Lower'] - prev['BB_Lower']
        
        slope_up2 = bollinger_upper_slope > 0 
        # 고점 돌파 (최근 5일 고점)
        recent_close_high = df['High'].iloc[-6:-1].max()
        cond8 = last['Close'] > recent_close_high
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.7  # 윗꼬리 80% 이상이면 제외
        
        cond9 = last['Close'] > last_resistance
        cond10 = prev['min_15d_close_minus_ema60'] < 0

        # ✅ 최종 매수 조건
        buy_signal = all([long_trend, crossover, not cond7, cond6, slope_up, volume_good, cond5, slope_up2])

        # 비교용 버전
        if version == 2:
            buy_signal = buy_signal and cond10
        
        return buy_signal, None
    

    def ema_crossover_trading_v2(self, df, last_resistance):
        """ 눌림 비교 """

        if len(df) < 3:
            return False, None

        # if last_resistance is None:
        #     return False, None
        
        # 추가
        df["close_minus_ema60"] = df["Close"] - df["EMA_60"]
        df["ema5_minus_ema60"] = df["EMA_5"] - df["EMA_60"]
        df["min_15d_close_minus_ema60"] = (
            df["close_minus_ema60"].rolling(window=15).min()
        )
        df["min_20d_ema5_minus_ema60"] = (
            df["ema5_minus_ema60"].rolling(window=20).min()
        )
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]

        cond1 = last['Close'] > last['EMA_5']
        cond2 = prev['Close'] <= prev['EMA_5']
        cond3 = prev_prev['Close'] <= prev_prev['EMA_5']
        # cond4 = prev['min_15d_close_minus_ema60'] < 0
        # cond4 = prev['min_20d_ema5_minus_ema60'] < 0

        cond5 = last['EMA_5'] > prev['EMA_5']
        cond6 = last['EMA_20'] > prev['EMA_20']
        cond7 = last['EMA_60'] > prev['EMA_60']
        cond8 = last['EMA_120'] > prev['EMA_120']

        cond9 = last['EMA_5'] > last['EMA_120']
        cond10 = last['EMA_60'] > last['EMA_120']
        cond11 = last['EMA_20'] / last['EMA_60'] < 1.1

        buy_signal = cond1 and cond2 and cond3 and cond5 and cond8 and cond10 and cond11
        
        return buy_signal, None
    

    def anti_retail_ema_entry(self, df):
        """
        매수 조건:
        - 고점 수평선(horizontal_high)을 돌파
        - 현재 종가(price)가 EMA_5 위에 위치

        Parameters:
        - df: 반드시 'price', 'horizontal_high', 'EMA_5' 컬럼 포함 (최신 데이터가 마지막 row)

        Returns:
        - (bool, str): (매수 여부, 매수 사유)
        """
        if len(df) < 3:
            return False, None  # 데이터 부족

        # if resistance is None:
        #     return False, None
        if 'volume_MA5' not in df.columns:
            df['volume_MA5'] = df['Volume'].rolling(window=5).mean()
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
            
        # cond1 = last["Close"] > resistance >= prev['Close']
        cond1 = prev["Close"] >= prev["Open"]
        cond2 = last["Close"] > last["EMA_5"]
        cond3 = last['Close'] > last['Open']
        cond4 = prev['Volume'] > prev_prev['Volume']
        cond5 = last["EMA_55_Slope_MA"] > 0.4
        cond7 = last['EMA_10'] > last['EMA_20'] and prev['EMA_10'] <= prev['EMA_20']
                # 📌 정배열 조건
                
        # if prev["Close"] < prev["EMA_89"]:
        #     cond6 = last["Close"] >= last["EMA_89"]
        # else:
        #     cond6 = True
        
        cond6 = prev["Close"] <= prev["EMA_60"] and last["Close"] > last["EMA_60"]
                # ✅ EMA 배열이 역배열일 경우 매수 제외 (EMA_89 > EMA_55 > EMA_5 > EMA_13 > EMA_21)
        is_bad_arrangement = (
            last["EMA_60"] > last["EMA_50"] > last['EMA_5'] >  last["EMA_10"] > last["EMA_20"]
        )
        cond8 = not is_bad_arrangement
        
        cond9 = last['EMA_120'] > last["EMA_60"] > last["EMA_10"] > last["EMA_20"]
        #cond9 = last['EMA_89'] > last["EMA_55"] > last['EMA_5'] > last["EMA_13"] > last["EMA_21"]        
                # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema50_slope = last['EMA_60'] - prev['EMA_60']
        ema120_slope = last['EMA_120'] - prev['EMA_120']
        cond10 = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0 and ema120_slope > 0
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        cond11  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
        
        cond12 = last["EMA_55_Slope_MA"] > 0.03 and last["EMA_89_Slope_MA"] > -0.02
        
        under_period = df.iloc[-31:-1]  # 전날까지 15일
        cond13 = all(under_period["EMA_13"] < under_period["EMA_21"])
        cond14 = last['Volume'] > last['volume_MA5'] and last['Volume'] > prev['Volume']
        
        # 고점 돌파 (최근 20일 고점)
        recent_high = df['High'].iloc[-26:-1].max()
        cond15 = last['Close'] > recent_high > prev['Close']
        
        cond16 = last['EMA_21'] > last['EMA_55'] and prev['EMA_21'] <= prev['EMA_55']
        cond17 = cond16 or cond7
        
            # ✅ 정배열 조건 확인
        is_bullish = (
            last['EMA_13'] > last['EMA_21'] > last['EMA_55'] > last['EMA_89']
        )

        if is_bullish:
            # 🔍 EMA_5가 EMA_13을 상향 돌파하는 순간
            crossed_up = prev['EMA_5'] <= prev['EMA_13'] and last['EMA_5'] > last['EMA_13']
        else:
            crossed_up = True
    
        buy_signal = all([cond7, cond6, cond9, cond3, cond11, cond10])
        
        return buy_signal, None

    def trendline_breakout_trading(self, df, resistance):
        """
        매수 조건:
        - 고점 수평선(horizontal_high)을 돌파
        - 현재 종가(price)가 EMA_5 위에 위치
        """
        if len(df) < 2:
            return False, None  # 데이터 부족

        if resistance is None:
            return False, None
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]

        cond1 = last["Close"] > resistance >= prev['Close']
        cond2 = last["Close"] > last["EMA_5"]
        cond3 = last['Close'] > last['Open']
        cond4 = prev['Volume'] > prev_prev['Volume']
        cond5 = last["EMA_55_Slope_MA"] > 0.4
                # 📌 정배열 조건
        if last["Close"] > last["EMA_55"]:
            cond6 = last["EMA_5"] > last["EMA_13"] > last["EMA_21"] > last['EMA_89']
        else:
            cond6 = True  # 종가가 EMA_55 아래에 있으면 정배열 조건은 적용하지 않음
            
        cond7 =  (prev['EMA_13'] <= prev['EMA_21'] and
        last['EMA_13'] > last['EMA_21'])
    
        buy_signal = all([cond1, cond3, cond5,cond6, cond7])
        
        return buy_signal, None
    
    def should_buy(self, df, high_trendline, last_resistance):
        """
        - 하락 고점 추세선을 상향 돌파 + 최근 수평 고점도 돌파
        """
        if len(df) < 10 or 'horizontal_high' not in df.columns:
            return False, None

        #current_idx = len(df) - 1
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # 고점 추세선 연장값
        
        if high_trendline is None:
            return False, None

        # # 가장 최근의 수평 고점
        # confirmed_highs = df.iloc[:current_idx - 5][df['horizontal_high'].notna()]
        # if confirmed_highs.empty:
        #     return False, None
        # last_resistance = confirmed_highs['horizontal_high'].iloc[-1]
        print(f"high_trendline: {high_trendline}")

        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema50_slope = last['EMA_55'] - prev['EMA_55']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0 and ema60_slope > 0
        slope_up2 = last['EMA_5'] - prev['EMA_5']
        
            # ✅ 조건 3-1: EMA_50, EMA_60 기울기 평균도 양수여야 함
        slope_ma_up = (
            last['EMA_55_Slope_MA'] > 0
            and last['EMA_60_Slope_MA'] > 0
        )
        
        # 조건
        cond1 = prev['Close'] <= high_trendline  # 하락추세선 아래 → 상향 돌파
        cond2 = last['Close'] > high_trendline
        cond3 = last['Close'] >= last_resistance  # 수평 고점도 돌파
        cond4 = last['Close'] > last['Open']     # 양봉
        cond5 = last['Volume'] > prev['Volume']
        buy_signal = all([cond1, cond2, cond4, cond5, slope_up2])
        
        return buy_signal, None
    

    def should_buy_break_high_trend(self, df):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        period = 20

        df[f"max_{period}d_close"] = df["Close"].rolling(window=period).max()
        df["max_20d_open_close"] = (
            pd.concat([df["Close"], df["Open"]], axis=1)  # 2개 컬럼 합치기
            .max(axis=1)                                  # 각 날의 Close vs Open 중 큰 값
            .rolling(window=20)                           # 20일치 윈도우
            .max()
        )
        df["min_20d_open_close"] = (
            pd.concat([df["Close"], df["Open"]], axis=1)
            .min(axis=1)             # 일자별 시가/종가 중 작은 값
            .rolling(window=20)
            .min()                   # 최근 20일 중 최소값
        )
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        d_2_prev = df.iloc[-3]

        cond1 = (last["Close"] == last[f"max_{period}d_close"])
        cond2 = (prev["Close"] < prev[f"max_{period}d_close"])
        cond3 = (d_2_prev["Close"] < d_2_prev[f"max_{period}d_close"])
        cond4 = (last['Close'] > last['Open'])
        cond5 = (last['Close'] / prev['Close'] < 1.15) # 15% 이상 상승 제외
        cond10 = (prev['max_20d_open_close'] / prev['min_20d_open_close'] < 1.1) # d-1일 기준 최근 20일 변동성 10% 이하
        
        cond6 = (last['EMA_5'] > last['EMA_20'] and last['EMA_20'] > last['EMA_60'])
        cond7 = last['EMA_5'] > prev['EMA_5']
        cond8 = last['EMA_20'] > prev['EMA_20']
        cond9 = last['EMA_60'] > prev['EMA_60']
        
        # 최종 조건
        buy_signal = cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7 and cond8 and cond9 and cond10

        return buy_signal, None

    
    def weekly_trading(self, df, last_resistance):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if last_resistance is None:
            return False, None
        
        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: 거래대금 계산(30억 이상)
        trade_value = close_price * volume

        # 조건 2: EMA_10이 EMA_20 상향 돌파
        cross_up = (
            prev['EMA_10'] <= prev['EMA_20'] and
            last['EMA_10'] > last['EMA_20']
        )

        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_5'] - prev['EMA_5']
        ema20_slope = last['EMA_10'] - prev['EMA_10']
        ema50_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0 and ema60_slope > 0

        # 조건 4: 거래량 증가
        volume_up = last['Volume'] > last['Volume_MA5']
        volume_up2 = last['Volume'] > prev['Volume']
        
        # ❌ 조건 5: 당일 윗꼬리 음봉 제외, 윗꼬리 조건 추가
        is_bearish = last['Close'] > last['Open'] and prev['Close'] > prev['Open']
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.7  # 윗꼬리 80% 이상이면 제외
        
        
        # 고점 돌파 (최근 20일 고점)
        recent_high = df['High'].iloc[-16:-1].max()
        cond15 = last['Close'] > recent_high

        cond16 = last['Close'] > last_resistance
        # 최종 조건
        buy_signal = all([cross_up, slope_up, is_bearish, not_long_upper_shadow, volume_up , volume_up2, cond16 ])

        return buy_signal, None
    
    def trend_entry_trading(self, df, lower_threshold_ratio = -1.00, upper_threshold_ratio = 1.00):
        """
        이름 : 상승추세형 매수
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록
        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()

        df[f"max_{15}d_close"] = df["Close"].rolling(window=15).max()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: 거래대금 계산(30억 이상)
        trade_value = close_price * volume

        # 조건 2: EMA_10이 EMA_20 상향 돌파
        cross_up = (
            prev['EMA_10'] <= prev['EMA_20'] and
            last['EMA_10'] > last['EMA_20']
        )

        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_5'] - prev['EMA_5']
        ema20_slope = last['EMA_10'] - prev['EMA_10']
        ema50_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema50_slope > 0 and ema60_slope > 0

        # 조건 4: 거래량 증가
        # volume_up = last['Volume'] > last['Volume_MA5']
        # volume_up2 = last['Volume'] > prev['Volume']
        
        # ❌ 조건 5: 당일 윗꼬리 음봉 제외, 윗꼬리 조건 추가
        is_bearish = last['Close'] > last['Open']

        # 상승률 확인
        rate = (last['Close'] - last['Open']) / last['Open'] # 0.05  # 5% 이상 상승
        change_ratio_check = rate >= lower_threshold_ratio and rate <= upper_threshold_ratio
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외

        # 최종 조건
        buy_signal = cross_up and slope_up and is_bearish

        return buy_signal, None
    

    def trend_entry_trading_v2(self, df, period):
        """
        이름 : EMA 상승 돌파
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록
        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()

        df[f"max_{10}d_close"] = df["Close"].rolling(window=10).max()
        df[f"max_{5}d_close"] = df["Close"].rolling(window=5).max()
        df["EMA_diff_20_5"] = df["EMA_20"] - df["EMA_5"]
        df[f"min{9}d_EMA_diff_20_5"] = df["EMA_diff_20_5"].rolling(window=9).min()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # cond1 = last['EMA_5'] > last['EMA_20']
        # cond2 = prev['EMA_5'] < prev['EMA_20']
        # cond3 = last['Close'] == last[f"max_{10}d_close"]
        # cond4 = last['EMA_5'] > prev['EMA_5']
        # cond5 = last['EMA_20'] > prev['EMA_20']
        # # cond6 = last['EMA_60'] > prev['EMA_60']
        # # cond6 = last['Close'] / last['EMA_20'] < 1.09
        # cond7 = last['Close'] >= last['Open']
        # cond8 = (last['High'] - last['Close']) < (last['Close'] - last['Open']) * 2
        # cond9 = last['EMA_60'] > prev['EMA_60']
        # cond10 = prev[f"min{9}d_EMA_diff_20_5"] > 0
        
        cond1 = last['Close'] > last[f'EMA_{period}']
        cond2 = prev['Close'] < prev[f'EMA_{period}']
        cond3 = last['Close'] == last[f"max_{5}d_close"]

        buy_signal = cond1 and cond2 and cond3

        return buy_signal, None
    
    
    def new_trading(self, df):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: 거래대금 계산(30억 이상)
        trade_value = close_price * volume

        # 조건 2: EMA_10이 EMA_20 상향 돌파
        cross_up = (
            prev['EMA_10'] <= prev['EMA_20'] and
            last['EMA_10'] > last['EMA_20']
        )

        # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        ema120_slope = last['EMA_120'] - prev['EMA_120']
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema120_slope > 0 and ema60_slope > 0

        # 조건 4: 거래량 증가
        volume_up = last['Volume'] > last['Volume_MA5']
        volume_up2 = last['Volume'] > prev['Volume']
        
        # ❌ 조건 5: 당일 윗꼬리 음봉 제외, 윗꼬리 조건 추가
        is_bearish = last['Close'] > last['Open']
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외

        # # 윗꼬리, 아랫꼬리 계산
        # upper_wick = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        # lower_wick = (min(last['Open'], last['Close']) - last['Low']) / (last['High'] - last['Low'] + 1e-6)
    
        # gap_threshold = 0.05
        # # 조건 1: 전일 대비 시초가 갭업
        # gap_up = last['Open'] > prev['Close'] * (1 + gap_threshold)
        
        # wick_ratio_threshold =0.4
        # has_long_wick = lower_wick >= wick_ratio_threshold
        
        bollinger_upper_slope = last['BB_Upper'] - prev['BB_Upper']
        bollinger_lower_slope = last['BB_Lower'] - prev['BB_Lower']
        
        slope_up2 = bollinger_upper_slope > 0
        # 최종 조건
        buy_signal = cross_up and slope_up and volume_up and is_bearish and volume_up2 and not_long_upper_shadow and slope_up2

        return buy_signal, None
    
    def sma_crossover_trading(self, df, last_resistance):
        if len(df) < 2:
            return False, None

        # if last_resistance is None:
        #     return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        # ✅ 중장기 정배열 조건
        long_trend = (
            last['SMA_10'] > last['SMA_20'] > last['SMA_60'] > last['SMA_120']
        )
        
        print(f"last['SMA_120']: {last['SMA_120']}")

        # ✅ EMA_5가 전일 EMA_13 아래에 있다가 당일 상향 돌파
        crossover = prev['Close'] <= prev['SMA_5'] and last['Close'] > last['SMA_5']

        # ✅ 종가가 EMA_5, EMA_13 위에 있어야 신뢰도 ↑
        price_above = last['Close'] > last['SMA_5'] and last['Close'] > last['SMA_10']

        # ✅ 거래량 조건 (5일 평균 이상 & 전일보다 증가)
        volume_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
        volume_good = last['Volume'] > volume_ma5 and last['Volume'] > prev['Volume']

        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        cond5  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
        cond6 = last['Close'] > last["Open"]
        
        cond7 = prev_prev['Close'] >= prev_prev['SMA_5'] and prev['Close'] <= prev['SMA_5'] and last['Close'] > last['SMA_5']
        
                # 조건 3: EMA 기울기 양수
        sma10_slope = last['SMA_10'] - prev['SMA_10']
        sma20_slope = last['SMA_20'] - prev['SMA_20']
        sma60_slope = last['SMA_60'] - prev['SMA_60']
        sma120_slope = last['SMA_120'] - prev['SMA_120']
        
        slope_up = sma10_slope > 0 and sma20_slope > 0 and sma60_slope > 0 and sma120_slope > 0
        
        bollinger_upper_slope = last['BB_Upper'] - prev['BB_Upper']
        bollinger_lower_slope = last['BB_Lower'] - prev['BB_Lower']
        
        slope_up2 = bollinger_upper_slope > 0 
        # 고점 돌파 (최근 5일 고점)
        recent_close_high = df['High'].iloc[-6:-1].max()
        cond8 = last['Close'] > recent_close_high
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.7  # 윗꼬리 80% 이상이면 제외
        
        cond9 = last['Close'] > last_resistance
        # ✅ 최종 매수 조건
        buy_signal = all([long_trend, crossover, not cond7, cond6, slope_up, volume_good, cond5, slope_up2])
        
        return buy_signal, None
    
    def wma_crossover_trading(self, df, last_resistance):
        if len(df) < 2:
            return False, None

        if last_resistance is None:
            return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        # ✅ 중장기 정배열 조건
        long_trend = (
            last['WMA_10'] > last['WMA_20'] > last['WMA_60'] > last['WMA_120']
        )

        # ✅ EMA_5가 전일 EMA_13 아래에 있다가 당일 상향 돌파
        crossover = prev['Close'] <= prev['WMA_5'] and last['Close'] > last['WMA_5']

        # ✅ 종가가 EMA_5, EMA_13 위에 있어야 신뢰도 ↑
        price_above = last['Close'] > last['WMA_5'] and last['Close'] > last['WMA_10']

        # ✅ 거래량 조건 (5일 평균 이상 & 전일보다 증가)
        volume_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
        volume_good = last['Volume'] > volume_ma5 and last['Volume'] > prev['Volume']

        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        cond5  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
        cond6 = last['Close'] > last["Open"]
        
        cond7 = prev_prev['Close'] >= prev_prev['WMA_5'] and prev['Close'] <= prev['WMA_5'] and last['Close'] > last['WMA_5']
        
                # 조건 3: EMA 기울기 양수
        sma10_slope = last['WMA_10'] - prev['WMA_10']
        sma20_slope = last['WMA_20'] - prev['WMA_20']
        sma60_slope = last['WMA_60'] - prev['WMA_60']
        sma120_slope = last['WMA_120'] - prev['WMA_120']
        
        slope_up = sma10_slope > 0 and sma20_slope > 0 and sma60_slope > 0 and sma120_slope > 0
        
        bollinger_upper_slope = last['BB_Upper'] - prev['BB_Upper']
        bollinger_lower_slope = last['BB_Lower'] - prev['BB_Lower']
        
        slope_up2 = bollinger_upper_slope > 0 
        # 고점 돌파 (최근 5일 고점)
        recent_close_high = df['High'].iloc[-6:-1].max()
        cond8 = last['Close'] > recent_close_high
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.7  # 윗꼬리 80% 이상이면 제외
        
        cond9 = last['Close'] > last_resistance
        # ✅ 최종 매수 조건
        buy_signal = all([long_trend, crossover, not cond7, cond6, slope_up, volume_good, cond5, slope_up2])
        
        return buy_signal, None
    
    def ema_crossover_trading2(self, df, last_resistance):
        if len(df) < 2:
            return False, None

        # if last_resistance is None:
        #     return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        # ✅ 중장기 정배열 조건
        long_trend = (
            last['EMA_5'] > last['EMA_10'] > last['EMA_20'] > last['EMA_60'] > last['EMA_120'] 
        )


        # ✅ EMA_5가 전일 EMA_13 아래에 있다가 당일 상향 돌파
        crossover = prev['Close'] <= prev['EMA_5'] and last['Close'] > last['EMA_5']

        # ✅ 종가가 EMA_5, EMA_13 위에 있어야 신뢰도 ↑
        price_above = last['Close'] > last['EMA_5'] and last['Close'] > last['EMA_10']

        # ✅ 거래량 조건 (5일 평균 이상 & 전일보다 증가)
        volume_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
        volume_good = last['Volume'] > volume_ma5 and last['Volume'] > prev['Volume']

        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        cond5  = upper_shadow_ratio <= 0.8  # 윗꼬리 80% 이상이면 제외
        cond6 = last['Close'] > last["Open"]
        
        cond7 = prev_prev['Close'] >= prev_prev['EMA_5'] and prev['Close'] <= prev['EMA_5'] and last['Close'] > last['EMA_5']
        
                # 조건 3: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        ema120_slope = last['EMA_120'] - prev['EMA_120']
        
        slope_up = ema10_slope > 0 and ema20_slope > 0 and ema60_slope > 0 and ema120_slope > 0
        
        bollinger_upper_slope = last['BB_Upper'] - prev['BB_Upper']
        bollinger_lower_slope = last['BB_Lower'] - prev['BB_Lower']
        
        slope_up2 = bollinger_upper_slope > 0 
        # 고점 돌파 (최근 5일 고점)
        recent_close_high = df['High'].iloc[-6:-1].max()
        cond8 = last['Close'] > recent_close_high
        
        upper_shadow_ratio = (last['High'] - max(last['Open'], last['Close'])) / (last['High'] - last['Low'] + 1e-6)
        not_long_upper_shadow  = upper_shadow_ratio <= 0.7  # 윗꼬리 80% 이상이면 제외
        
        cond9 = last['Close'] > last_resistance
        
        # ✅ 60일간 EMA_5 / EMA_120 비율의 최대값이 1.2 미만
        ratio_max_60 = (df['EMA_5'] / df['EMA_120']).iloc[-60:].max()
        cond10 = ratio_max_60 < 1.2        
        # ✅ 최종 매수 조건
        buy_signal = all([long_trend, crossover, not cond7, cond6, slope_up, volume_good, cond5, slope_up2, cond10])
        
        return buy_signal, None
    
    def day120_trend_line(self, df):
        if len(df) < 2:
            return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        
        cond1 = last['EMA_60'] > prev['EMA_60']
        cond2 = last['EMA_120'] > prev['EMA_120']
        cond3 = last['Close'] < last['EMA_60'] * (1+0.02)
        
        # ✅ 최종 매수 조건
        buy_signal = all([cond1, cond2, cond3])
        
        return buy_signal, None
    
    def day120_trend_line_2(self, df):
        if len(df) < 2:
            return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        
        cond1 = last['EMA_60'] > prev['EMA_60']
        cond2 = last['EMA_120'] > prev['EMA_120']
        cond3 = last['Close'] < last['EMA_120'] * (1+0.02)
        # ✅ 최종 매수 조건
        buy_signal = all([cond1, cond2, cond3])
        
        return buy_signal, None
    
    def day120_trend_line_2(self, df):
        if len(df) < 2:
            return False, None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        
        cond1 = last['EMA_60'] > prev['EMA_60']
        cond2 = last['EMA_120'] > prev['EMA_120']
        cond3 = last['Close'] < last['EMA_120'] * (1+0.02)
        # ✅ 최종 매수 조건
        buy_signal = all([cond1, cond2, cond3])
        
        return buy_signal, None          
    
    def new_trend_entry(self, df):
        """
        이름 : new 상승추세
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록
        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 1: EMA 기울기 양수
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema60_slope = last['EMA_60'] - prev['EMA_60']
        slope_up = last['EMA_10'] - last['EMA_20'] > 0 and ema10_slope > 0 and ema20_slope > 0 and ema60_slope > 0

        # 조건 2: 거래량 증가
        cond5 = last['Close'] < last['EMA_10'] * (1+0.02)
        cond6 = abs(last['Close'] - last['Open']) < last['EMA_10'] * (1+0.03)
        
        # 최종 조건
        buy_signal = slope_up and cond5 and cond6

        return buy_signal, None
    
    def new_trend_entry2(self, df):
        """
        EMA 배열 + 상향 돌파 기반 매수 신호 생성 및 사유 기록

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])

        # 조건 2: 거래량 증가
        cond5 = last['EMA_60'] > prev['EMA_60']
        cond6 = prev['EMA_60'] <= prev_prev['EMA_60']
        
        # 최종 조건
        buy_signal = cond5 and cond6

        return buy_signal, None
    
    def congestion_trading(self, df):
        """
        최대값/최소값 < 1.03
        최소값이 120 이평보다 크다
        120 이평 상승

        """

        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]
        trade_date = last.name.date()
        
        close_price = float(last['Close'])
        volume = float(last['Volume'])
        
        emas = [last['EMA_5'], last['EMA_10'], last['EMA_20'], last['EMA_60']]
        max_price = max(emas)
        min_price = min(emas)
        # 조건 2: 거래량 증가
        cond1 = last['EMA_120'] > prev['EMA_120']
        cond2 = min_price > last['EMA_120']
        cond3 = max_price /  min_price < 1.03
        cond4 = last['EMA_5'] > prev['EMA_5']
        cond5 = abs(last['Open'] - last['Close']) < last['EMA_60'] * 0.01
        
        # 최종 조건
        buy_signal = cond1 and cond2 and cond3 and cond4 and cond5

        return buy_signal, None
    

    def combined_new_trend_entry(self, df):
        
        check_period = 10
        first_buy_signal, _ = self.new_trend_entry(df)

        final_buy_signal = False

        if first_buy_signal: # new 상승 추세가 매수 신호가 발생하면
            for i in range(1, check_period + 1):
                final_buy_signal, _ = self.trend_entry_trading(df.iloc[:-i], lower_threshold_ratio=0.06)
                if final_buy_signal:
                    print(f"✅ {i}일 전 상승 추세형 매수 신호 발생")
                    break
        
        return final_buy_signal, None


    def detect_large_volume_trades(self, df):
        
        """
        이름 : 대량 거래
        거래량 급증 기반 매수 신호 생성
        """

        if len(df) < 2:
            return False, None

        if 'Volume_MA20' not in df.columns:
            df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        cond1 = last['Volume'] > prev['Volume_MA20'] * 3
        cond2 = last['Volume'] > prev['Volume']

        buy_signal = cond1 and cond2

        return buy_signal, None


    def all_time_high_trading(self, df, days=10, period=20):
        """
        신고가형 매수
        D-1 일부터 D-n 일까지 n일간 60일 신고가 아닐 조건
        """
        if len(df) < 2:
            return False, None

        df[f"max_{period}d_close"] = df["Close"].rolling(window=period).max()
        df[f"min_5d_close"] = df["Close"].rolling(window=5).min()
        df[f"low_minus_EMA_120"] = df["Low"] - df[f"EMA_120"]

        if 'Volume_MA20' not in df.columns:
            df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        cond1 = True

        for i in range(1, 4):   # d ~ d-9 까지 10개
            idx = -1 * i
            close = df.iloc[idx]["Close"]
            max_close = df.iloc[idx][f"max_{period}d_close"]
            if i == 1:
                if close == max_close: # d 일은 60일 신고가여야 함
                    cond1 = True
                else:
                    cond1 = False
                    break
            else:
                if close < max_close:
                    cond1 = True
                else:
                    cond1 = False
                    break
        
        cond2 = df.iloc[-21-1:-1-1][f"low_minus_EMA_120"].min() < 0

        # ema 조건
        cond3 = last["EMA_5"] > last["EMA_20"]
        cond4 = last["EMA_20"] > last["EMA_60"]
        cond5 = last["EMA_20"] > prev["EMA_20"]
        cond6 = last["EMA_60"] > prev["EMA_60"]

        cond7 = last["Volume"] > prev["Volume_MA20"] * 3
        cond8 = last["Volume"] > prev["Volume"]

        cond9 = last["Close"] > last["Open"]
        cond10 = last["Close"] / prev["Close"] < 1.15
        
        # 60일 전 데이터가 필요
        if len(df) < 61:
            cond11 = False
        else:
            cond11 = last["EMA_60"] < df.iloc[-61]["EMA_60"]
        
        cond12 = prev["min_5d_close"] < prev["EMA_60"]

        buy_signal = cond1 and cond9 and cond10 and cond11 and cond12

        return buy_signal, None


    def williams_trading(self, df):
        
        if df.shape[0] < 3:
            print("❌ 데이터가 부족해서 trend_entry_trading 조건 계산 불가")
            return False, None

        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev_prev = df.iloc[-3]

        cond1 = last['Close'] > last['Open'] + (prev['High'] - prev['Low']) * 0.5
        cond2 = prev['Close'] < prev['Open']

        final_buy_signal = cond1 and cond2
        
        return final_buy_signal, None
    

### -------------------------------------------------------------매도로직-------------------------------------------------------------

    def should_sell_break_low_trend(self, df, window=5):
        """
        최근 저점들로 만든 추세선 이탈 시 매도
        """
        if len(df) < window + 1:
            return False, None

        lows = df['Low'].iloc[-window - 1:-1].values
        x = np.arange(len(lows))
        trendline_price = self.fit_trendline(x, lows)

        close_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]

        # 이전엔 추세선 위, 지금은 이탈
        if prev_close >= trendline_price and close_price < trendline_price:
            return True, f"📉 저점 추세선 이탈 매도 (기준가: {trendline_price:.2f})"

        return False, None
    
    def horizontal_low_sell(self, df):
        """
        조건: 이전 종가 >= 수평 고점, 현재 종가 < 수평 고점 → 저항 실패
        """
        if len(df) < 3 or 'horizontal_low' not in df.columns:
            return None, False

        last = df.iloc[-1]
        prev = df.iloc[-2]

        resistance_row = df[df['horizontal_low'].notna()].iloc[-1:]
        if resistance_row.empty:
            return None, False

        support = resistance_row['horizontal_low'].values[0]

        sell_signal = prev['Close'] >= support > last['Close']

        return None, sell_signal
    
    def break_prev_low(self, df):
        """
        볼린저밴드 기반 매도 신호
        전일 종가의 위치에 따라 상단, 중단, 하단 이탈 여부를 판단

        df: DataFrame with columns ['Close', 'BB_Upper', 'BB_Middle', 'BB_Lower']
        return: reason(str or None), sell_signal (bool)
        """
        if len(df) < 3:
            return None, False  # 데이터 부족

        last = df.iloc[-1]
        prev = df.iloc[-2]

        reason = None
        sell_signal = False

        # ✅ 조건 1: 상단선 돌파 후 하향 이탈
        if prev['Close'] > prev['BB_Upper'] and last['Close'] < last['BB_Upper']:
            reason = (
                f"📉 상단 돌파 후 하락 → 매도: "
                f"전날 {prev['Close']:.2f} > 상단 {prev['BB_Upper']:.2f}, "
                f"오늘 {last['Close']:.2f} < 상단 {last['BB_Upper']:.2f}"
            )
            sell_signal = True

        # ✅ 조건 2: 중단~상단 사이 → 중단 이탈
        elif (
            prev['Close'] < prev['BB_Upper'] and
            prev['Close'] > prev['BB_Middle'] and
            last['Close'] < last['BB_Middle']
        ):
            reason = (
                f"📉 중단선 하향 이탈 → 매도: "
                f"전날 {prev['Close']:.2f} ∈ ({prev['BB_Middle']:.2f}, {prev['BB_Upper']:.2f}), "
                f"오늘 {last['Close']:.2f} < 중단 {last['BB_Middle']:.2f}"
            )
            sell_signal = True

        # ✅ 조건 3: 하단 이탈
        elif (
            prev['Close'] < prev['BB_Middle'] and
            prev['Close'] > prev['BB_Lower'] and
            last['Close'] < last['BB_Lower']
        ):
            reason = (
                f"📉 하단선 하향 이탈 → 매도: "
                f"전날 {prev['Close']:.2f} ∈ ({prev['BB_Lower']:.2f}, {prev['BB_Middle']:.2f}), "
                f"오늘 {last['Close']:.2f} < 하단 {last['BB_Lower']:.2f}"
            )
            sell_signal = True

        return None, sell_signal
    
    def sell_on_support_break(self, df):
        """
        2차 지지선 이탈 + 거래량 실린 음봉 조건의 매도 시그널
        - s2_level: 피봇 지표 등으로 계산된 2차 지지선 값 (float)
        """
        if df.shape[0] < 3:
            print("❌ 캔들 데이터 부족")
            return False, None

        # ✅ 전일 고가, 저가, 종가로 Pivot, S2 계산
        prev = df.iloc[-2]
        prev_high = prev['High']
        prev_low = prev['Low']
        prev_close = prev['Close']
        P = (prev_high + prev_low + prev_close) / 3
        s2_level = P - (prev_high - prev_low)
    
        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()

        last = df.iloc[-1]
        
        # ✅ 조건 1: 2차 지지선 하회
        below_s2 = last['Close'] < s2_level

        # ✅ 조건 2: 음봉
        is_bearish_candle = last['Close'] < last['Open']

        # ✅ 조건 3: 거래량이 5일 평균 이상
        volume_heavy = last['Volume'] > prev['Volume']

        # ✅ 매도 시그널
        sell_signal = below_s2 and is_bearish_candle and volume_heavy

        return None, sell_signal
    
    def should_sell(self, df):
        """
        df: DataFrame with columns ['Close', 'EMA_5', 'EMA_10', 'Low']
        """
        if len(df) < 3:
            return None, False  # 데이터 부족

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # 조건 1: 5일 EMA 데드크로스
        dead_cross = prev['EMA_10'] > prev['EMA_20'] and last['EMA_10'] < last['EMA_20']
        
        # 조건 3: EMA 기울기
        ema10_slope = last['EMA_10'] - prev['EMA_10']
        ema20_slope = last['EMA_20'] - prev['EMA_20']
        ema50_slope = last['EMA_55'] - prev['EMA_55']
        slope_up = ema10_slope <= 0 and ema20_slope <= 0 and ema50_slope <= 0

        sell_signal = dead_cross and slope_up
        
        return None, sell_signal
    
    def downtrend_sell_trading(self, df):
        """
        윗꼬리 긴 음봉일 때 매도 신호 발생
        """
        if len(df) < 3:
            return None, False  # 데이터 부족

        last = df.iloc[-1]
        
        open_price = last['Open']
        close_price = last['Close']
        high = last['High']
        low = last['Low']

        # 조건 2: 윗꼬리 비율이 50% 이상
        upper_shadow = high - max(open_price, close_price)
        body = abs(close_price - open_price)                # 몸통 길이
        total_range = high - low                # 전체 봉의 길이
        
        # 최종 조건
        sell_signal = upper_shadow >= body

        return None, sell_signal
    
    def top_reversal_sell_trading(self, df):
        """
        5일선이 10일 선 밑으로 갈 때
        """
        if len(df) < 3:
            return None, False  # 데이터 부족

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # 조건 1: 5일 EMA 데드크로스
        dead_cross = last['EMA_5'] < last['EMA_10'] and last['EMA_5'] > last['Close']

        sell_signal = dead_cross
        
        return None, sell_signal
    
    def sell_on_ema_break(self, df, period=5):
        """
        n일선 이탈 시 매도
        """
        if len(df) < 2:
            return None, False

        last = df.iloc[-1]

        sell_signal = last['Close'] < last[f'EMA_{period}']

        return None, sell_signal
    

    def ema_cross_sell(self, df, period_short=5, period_long=10):
        """
        df: DataFrame with columns ['Close', 'EMA_5', 'EMA_10', 'Low']
        5일선이 10일선 밑으로 갈 때
        """
        if len(df) < 3:
            return None, False  # 데이터 부족

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # 조건 1: 5일 EMA 데드크로스
        dead_cross = prev[f'EMA_{period_short}'] > prev[f'EMA_{period_long}'] and last[f'EMA_{period_short}'] < last[f'EMA_{period_long}']

        sell_signal = dead_cross
        
        return None, sell_signal