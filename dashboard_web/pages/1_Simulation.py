import sys
import os
import io
import streamlit as st
from io import StringIO
import matplotlib.pyplot as plt
import seaborn as sns
from st_aggrid import AgGrid, GridUpdateMode, GridOptionsBuilder
import pandas as pd
from datetime import datetime, date, timedelta
import pytz
import streamlit.components.v1 as components
from streamlit_lightweight_charts import renderLightweightCharts
import json
import random
import numpy as np
import plotly.express as px
import requests
import time
from pytz import timezone

# 프로젝트 루트를 PYTHONPATH에 추가
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.utils.dynamodb.crud import DynamoDBExecutor
from app.utils.dynamodb.model.auto_trading_model import AutoTrading
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol, StockSymbol2
from app.utils.dynamodb.model.trading_history_model import TradingHistory
from app.utils.dynamodb.model.simulation_history_model import SimulationHistory
from app.utils.dynamodb.model.user_info_model import UserInfo
from app.utils.dynamodb.model.auto_trading_balance_model import AutoTradingBalance
from app.utils.utils import setup_env


# env 파일 로드
setup_env()

backend_base_url = os.getenv('BACKEND_BASE_URL')

def initial_router():
    params = st.query_params
    is_logged_in = params.get("login", "false") == "true"
    current_page = params.get("page", "login")
    st.session_state["username"] = params.get("username", "Guest")
    
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = is_logged_in

    if st.session_state["authenticated"] and current_page == 'main':
        main()
    else:
        login_page()


def draw_lightweight_chart(data_df, assets, indicators):

    buy_signals = []    
    sell_signals = []

    holding = assets['account_holdings'][0]
    for trade in holding["trading_histories"]:
        if trade["trade_type"] == "BUY":
            # timestamp와 price(또는 avg_price 등)를 추출
            buy_signals.append((trade["timestamp_str"], trade["close_price"]))
        elif trade["trade_type"] == "SELL":
            # timestamp와 price(또는 avg_price 등)를 추출
            sell_signals.append((trade["timestamp_str"], trade["close_price"]))
    
    # 차트 color
    COLOR_BULL = 'rgba(236, 57, 72, 1)' # #26a69a
    COLOR_BEAR = 'rgba(74, 86, 160, 1)'  # #ef5350

    # Some data wrangling to match required format
    data_df = data_df.reset_index()
    data_df.columns = [col.lower() for col in data_df.columns] #모두 소문자로 수정
    
    data_df['time'] = pd.to_datetime(data_df['time']).dt.strftime('%Y-%m-%d')

    # export to JSON format
    candles = json.loads(data_df.to_json(orient = "records"))

    bollinger_band_upper = json.loads(data_df.dropna(subset=['bb_upper']).rename(columns={"bb_upper": "value",}).to_json(orient = "records"))
    bollinger_band_middle = json.loads(data_df.dropna(subset=['bb_middle']).rename(columns={"bb_middle": "value",}).to_json(orient = "records"))
    bollinger_band_lower = json.loads(data_df.dropna(subset=['bb_lower']).rename(columns={"bb_lower": "value",}).to_json(orient = "records"))

    # 차트 표시용 ema 데이터 추가
    for i in indicators:
        if i['type'] == 'ema' and i['draw_yn'] is True:
            i['data'] = json.loads(data_df.dropna(subset=[i['name']]).rename(columns={i['name']: "value"}).to_json(orient="records"))
        if i['type'] == 'sma' and i['draw_yn'] is True:
            i['data'] = json.loads(data_df.dropna(subset=[i['name']]).rename(columns={i['name']: "value"}).to_json(orient="records"))
    
    # sma_5 = json.loads(data_df.dropna(subset=['sma_5']).rename(columns={"sma_5": "value"}).to_json(orient="records"))
    # sma_20 = json.loads(data_df.dropna(subset=['sma_20']).rename(columns={"sma_20": "value"}).to_json(orient="records"))
    # sma_40 = json.loads(data_df.dropna(subset=['sma_40']).rename(columns={"sma_40": "value"}).to_json(orient="records"))
    # sma_200 = json.loads(data_df.dropna(subset=['sma_200']).rename(columns={"sma_200": "value"}).to_json(orient="records"))
    # sma_120 = json.loads(data_df.dropna(subset=['sma_120']).rename(columns={"sma_120": "value"}).to_json(orient="records"))
    
    rsi = json.loads(data_df.dropna(subset=['rsi']).rename(columns={"rsi": "value"}).to_json(orient="records"))
    macd = json.loads(data_df.dropna(subset=['macd']).rename(columns={"macd": "value"}).to_json(orient="records"))
    macd_signal = json.loads(data_df.dropna(subset=['macd_signal']).rename(columns={"macd_signal": "value"}).to_json(orient="records"))
    macd_histogram = json.loads(data_df.dropna(subset=['macd_histogram']).rename(columns={"macd_histogram": "value"}).to_json(orient="records"))
    stochastic_k = json.loads(data_df.dropna(subset=['stochastic_k']).rename(columns={"stochastic_k": "value"}).to_json(orient="records"))
    stochastic_d = json.loads(data_df.dropna(subset=['stochastic_d']).rename(columns={"stochastic_d": "value"}).to_json(orient="records"))
    mfi = json.loads(data_df.dropna(subset=['mfi']).rename(columns={"mfi": "value"}).to_json(orient="records"))

    temp_df = data_df
    temp_df['color'] = np.where(temp_df['open'] > temp_df['close'], COLOR_BEAR, COLOR_BULL)  # bull or bear
    volume = json.loads(temp_df.rename(columns={"volume": "value",}).to_json(orient = "records"))
    
    # 매매 마커 추가
    markers = []
    # for _, row in buy_signal_df.iterrows():
    for signal in buy_signals:
        marker = {
            # "time": row['time'],  # 'date' 열을 'time' 키로 변환
            "time": signal[0],  # 'date' 열을 'time' 키로 변환
            "position": "belowBar",  # 'position_type' 열을 'position' 키로 변환
            "color": "rgba(0, 0, 0, 1)",  # 'marker_color' 열을 'color' 키로 변환
            "shape": "arrowUp",  # 'marker_shape' 열을 'shape' 키로 변환
            "text": "B",  # 'type' 열을 'text' 키로 변환
            "size": 1  # 'size' 열을 'size' 키로 변환
        }
        markers.append(marker)

    # for _, row in sell_signal_df.iterrows():
    for signal in sell_signals:
        marker = {
            # "time": row['time'],  # 'date' 열을 'time' 키로 변환
            "time": signal[0],  # 'date' 열을 'time' 키로 변환
            "position": "aboveBar",  # 'position_type' 열을 'position' 키로 변환
            "color": "rgba(0, 0, 0, 1)",  # 'marker_color' 열을 'color' 키로 변환
            "shape": "arrowDown",  # 'marker_shape' 열을 'shape' 키로 변환
            "text": "S",  # 'type' 열을 'text' 키로 변환
            "size": 1  # 'size' 열을 'size' 키로 변환
        }
        markers.append(marker)

    markers.sort(key=lambda marker: marker['time'])

    print('markers:', markers)

    chartMultipaneOptions = [
        {
            # "width": 200, # 자동 너비 설정
            "height": 400,
            "layout": {
                "background": {
                    "type": "solid",
                    "color": 'white'
                },
                "textColor": "black"
            },
            "grid": {
                "vertLines": {
                    "color": "rgba(197, 203, 206, 0.5)"
                    },
                "horzLines": {
                    "color": "rgba(197, 203, 206, 0.5)"
                }
            },
            "crosshair": {
                "mode": 0
            },
            "priceScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)"
            },
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,             # 왼쪽 가장자리 고정 여부
                "fixRightEdge": True,
                "visible": True
            },
        },
        {
            # "width": 1000,
            "height": 150,
            "layout": {
                "background": {
                    "type": "solid",
                    "color": 'white'
                },
                "textColor": "black"
            },
            "grid": {
                "vertLines": {
                    "color": "rgba(197, 203, 206, 0.5)"
                    },
                "horzLines": {
                    "color": "rgba(197, 203, 206, 0.5)"
                }
            },
            "crosshair": {
                "mode": 0
            },
            "priceScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)"
            },
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,             # 왼쪽 가장자리 고정 여부
                "fixRightEdge": True,
                "visible": True
            },
            "watermark": {
                "visible": True,
                "fontSize": 15,
                "horzAlign": 'left',
                "vertAlign": 'top',
                "color": 'rgba(255, 99, 132, 0.7)',
                "text": 'Volume',
            }
        },
        {
            "height": 150,  # RSI 차트 높이 설정
            "layout": {
                "background": {"type": "solid", "color": 'white'},
                "textColor": "black"
            },
            "grid": {
                "vertLines": {"color": "rgba(197, 203, 206, 0.5)"},
                "horzLines": {"color": "rgba(197, 203, 206, 0.5)"}
            },
            "crosshair": {"mode": 0},
            "priceScale": {"borderColor": "rgba(197, 203, 206, 0.8)"},
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,
                "fixRightEdge": True,
                "visible": True
            },
            "watermark": {
                "visible": True,
                "fontSize": 15,
                "horzAlign": 'left',
                "vertAlign": 'top',
                "color": 'rgba(255, 99, 132, 0.7)',
                "text": 'RSI',
            }
        },
        {
            "height": 150,  # MACD 차트 높이 설정
            "layout": {
                "background": {"type": "solid", "color": 'white'},
                "textColor": "black"
            },
            "grid": {
                "vertLines": {"color": "rgba(197, 203, 206, 0.5)"},
                "horzLines": {"color": "rgba(197, 203, 206, 0.5)"}
            },
            "crosshair": {"mode": 0},
            "priceScale": {"borderColor": "rgba(197, 203, 206, 0.8)"},
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,
                "fixRightEdge": True,
                "visible": True
            },
            "watermark": {
                "visible": True,
                "fontSize": 15,
                "horzAlign": 'left',
                "vertAlign": 'top',
                "color": 'rgba(255, 99, 132, 0.7)',
                "text": 'MACD',
            }
        },
        {
            "height": 150,  # Stocastic 차트 높이 설정
            "layout": {
                "background": {"type": "solid", "color": 'white'},
                "textColor": "black"
            },
            "grid": {
                "vertLines": {"color": "rgba(197, 203, 206, 0.5)"},
                "horzLines": {"color": "rgba(197, 203, 206, 0.5)"}
            },
            "crosshair": {"mode": 0},
            "priceScale": {"borderColor": "rgba(197, 203, 206, 0.8)"},
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,
                "fixRightEdge": True,
                "visible": True
            },
            "watermark": {
                "visible": True,
                "fontSize": 15,
                "horzAlign": 'left',
                "vertAlign": 'top',
                "color": 'rgba(255, 99, 132, 0.7)',
                "text": 'Stocastic',
            }
        },
        {
            "height": 150,  # MFI 차트 높이 설정
            "layout": {
                "background": {"type": "solid", "color": 'white'},
                "textColor": "black"
            },
            "grid": {
                "vertLines": {"color": "rgba(197, 203, 206, 0.5)"},
                "horzLines": {"color": "rgba(197, 203, 206, 0.5)"}
            },
            "crosshair": {"mode": 0},
            "priceScale": {"borderColor": "rgba(197, 203, 206, 0.8)"},
            "timeScale": {
                "borderColor": "rgba(197, 203, 206, 0.8)",
                "barSpacing": 15,
                "fixLeftEdge": True,
                "fixRightEdge": True,
                "visible": True
            },
            "watermark": {
                "visible": True,
                "fontSize": 15,
                "horzAlign": 'left',
                "vertAlign": 'top',
                "color": 'rgba(255, 99, 132, 0.7)',
                "text": 'Mfi'
            }
        }
    ]

    seriesCandlestickChart = [
        {
            "type": 'Candlestick',
            "data": candles,
            "options": {
                "upColor": COLOR_BULL,
                "downColor": COLOR_BEAR,
                "borderVisible": False,
                "wickUpColor": COLOR_BULL,
                "wickDownColor": COLOR_BEAR
            },
            "markers": markers
        },
    ]
    
    def convert_color_hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
        """
        "#RRGGBB" 형식의 HEX 색상을 "rgba(R, G, B, A)" 문자열로 변환합니다.
        
        Args:
            hex_color (str): "#000000" 등 7자리 hex 색상
            alpha (float): 0.0 ~ 1.0 사이의 투명도 값

        Returns:
            str: rgba 문자열
        """

        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            raise ValueError("HEX 색상은 6자리여야 합니다. 예: #FF0000")
        
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

    # indicator 그리기
    for indicator in indicators:
        # Bollinger Band
        color = convert_color_hex_to_rgba(indicator['color_hex'])
        if "bollinger" in indicator['name']:
            seriesCandlestickChart.extend([
                {
                    "type": 'Line',
                    "data": bollinger_band_upper,
                    "options": {
                        "color": color,
                        "lineWidth": 0.5,
                        "priceScaleId": "right",
                        "lastValueVisible": False,
                        "priceLineVisible": False,
                    },
                },
                {
                "type": 'Line',
                "data": bollinger_band_middle,  # 중단 밴드 데이터
                "options": {
                    "color": color,  # 노란색
                    "lineWidth": 0.5,
                    "priceScaleId": "right",
                    "lastValueVisible": False, # 가격 레이블 숨기기
                    "priceLineVisible": False, # 가격 라인 숨기기
                    },
                },
                {
                    "type": 'Line',
                    "data": bollinger_band_lower,
                    "options": {
                        "color": color,
                        "lineWidth": 0.5,
                        "priceScaleId": "right",
                        "lastValueVisible": False,
                        "priceLineVisible": False,
                    },
                },
            ])
            
        # EMA
        if indicator['type'] == 'ema' and indicator['draw_yn'] is True:
            seriesCandlestickChart.append({
                "type": 'Line',
                "data": indicator['data'],
                "options": {
                    "color": color, #검은색
                    "lineWidth": 2,
                    "priceScaleId": "right",
                    "lastValueVisible": False,
                    "priceLineVisible": False,
                },
            })

        # SMA
        if indicator['type'] == 'sma' and indicator['draw_yn'] is True:
            seriesCandlestickChart.append({
                "type": 'Line',
                "data": indicator['data'],
                "options": {
                    "color": color, #검은색
                    "lineWidth": 2,
                    "priceScaleId": "right",
                    "lastValueVisible": False,
                    "priceLineVisible": False,
                },
            }) 
            
        # 📌 추세선 파라미터 입력
        lookback_prev = 7
        lookback_next = 7

        # 1. 고점/저점 수평선 추출
        high_lines, low_lines = find_horizontal_lines(data_df, lookback_prev, lookback_next)

        # 2. 중복 제거
        # high_lines = remove_similar_levels(high_lines, threshold=0.01)
        # low_lines = remove_similar_levels(low_lines, threshold=0.01)

        # # 3. 최근 기준으로 필터링
        # recent_dates = set(data_df['time'][-60:])
        # high_lines = [line for line in high_lines if line['time'] in recent_dates]
        # low_lines = [line for line in low_lines if line['time'] in recent_dates]

        # # 4. 상위 N개 선만 남김
        # high_lines = sorted(high_lines, key=lambda x: -x['value'])[:5]
        # low_lines = sorted(low_lines, key=lambda x: x['value'])[:5]

        # 5. 추세선 생성
        high_trendline = create_high_trendline(high_lines)
        low_trendline = create_low_trendline(low_lines)

        # 6. 시리즈에 추가
        if "horizontal_high" in indicator['name']:
            seriesCandlestickChart.extend(create_horizontal_line_segments(high_lines, candles))

        if "horizontal_low" in indicator['name']:
            seriesCandlestickChart.extend(create_horizontal_line_segments(low_lines, candles))
                
        # 조건에 따라 시리즈에 추가
        if "high_trendline" in indicator['name'] and high_trendline:
            seriesCandlestickChart.append(high_trendline)

        if "low_trendline" in indicator['name'] and low_trendline:
            seriesCandlestickChart.append(low_trendline)
                                    
    seriesVolumeChart = [
        {
            "type": 'Histogram',
            "data": volume,
            "options": {
                "priceFormat": {
                    "type": 'volume',
                },
                "priceScaleId": "", # set as an overlay setting,
                "priceLineVisible": False,
            },
            "priceScale": {
                "scaleMargins": {
                    "top": 0.1,
                    "bottom": 0,
                },
                "alignLabels": False
            },
        }
    ]

    # RSI 차트 시리즈 추가
    seriesRsiChart = [
        {
            "type": 'Line',
            "data": rsi,
            "options": {
                "color": 'rgba(0, 0, 0, 1)',
                "lineWidth": 1.5,
                "priceScaleId": "right",
                "lastValueVisible": True,
                "priceLineVisible": False,
            },
        },
        {
            "type": 'Line',
            "data": [{"time": row["time"], "value": 70} for row in rsi],  # 과매수 라인
            "options": {
                "color": 'rgba(200, 0, 0, 0.5)',  # 빨간색
                "lineWidth": 2,
                "priceScaleId": "right",
                "lastValueVisible": True,
                "priceLineVisible": False,
            },
        },
        {
            "type": 'Line',
            "data": [{"time": row["time"], "value": 30} for row in rsi],  # 과매도 라인
            "options": {
                "color": 'rgba(200, 0, 0, 0.5)',  # 빨간색
                "lineWidth": 2,
                "priceScaleId": "right",
                "lastValueVisible": True,
                "priceLineVisible": False,
            },
        },
    ]

    seriesMACDChart = [
        {
            "type": 'Line',
            "data": macd,
            "options": {
                "color": 'rgba(0, 150, 255, 1)', #파란색
                "lineWidth": 1.5,
                "priceLineVisible": False,
            }
        },
        {
            "type": 'Line',
            "data": macd_signal, 
            "options": {
                "color": 'rgba(255, 0, 0, 1)', #빨간색
                "lineWidth": 1.5,
                "priceLineVisible": False,
            }
        },
        {
            "type": 'Histogram',
            "data": macd_histogram,
            "options": {
                "priceLineVisible": False,
            }
        }
    ]

    seriesStochasticChart = [
        {
            "type": 'Line', 
            "data": stochastic_k, 
            "options": {
                "color": 'rgba(0, 150, 255, 1)', #파란색
                "lineWidth": 1.5,
                "priceLineVisible": False,
            }
        },
        {
            "type": 'Line', 
            "data": stochastic_d, 
            "options": {
                "color": 'rgba(255, 0, 0, 1)', #빨간색
                "lineWidth": 1.5,
                "priceLineVisible": False,
            }
        },
    ]

    seriesMfiChart = [
        {
            "type": 'Line', 
            "data": mfi, 
            "options": {
                "color": 'rgba(0, 150, 255, 1)', #파란색 
                "lineWidth": 1.5,
                "priceLineVisible": False,
            }
        },
        {
            "type": 'Line',
            "data": [{"time": row["time"], "value": 80} for row in mfi],  # 과매도 라인
            "options": {
                "color": 'rgba(200, 0, 0, 0.5)',  # 빨간색
                "lineWidth": 2,
                "priceScaleId": "right",
                "lastValueVisible": True,
                "priceLineVisible": False,
            },
        },
        {
            "type": 'Line',
            "data": [{"time": row["time"], "value": 20} for row in mfi],  # 과매수 라인
            "options": {
                "color": 'rgba(200, 0, 0, 0.5)',  # 빨간색
                "lineWidth": 2,
                "priceScaleId": "right",
                "lastValueVisible": True,
                "priceLineVisible": False,
            },
        },
    ]
    
    renderLightweightCharts([
        {
            "chart": chartMultipaneOptions[0],
            "series": seriesCandlestickChart
        },
        {
            "chart": chartMultipaneOptions[1],
            "series": seriesVolumeChart
        },
        {
            "chart": chartMultipaneOptions[2],
            "series": seriesRsiChart
        },
        {
            "chart": chartMultipaneOptions[3],
            "series": seriesMACDChart
        },
        {
            "chart": chartMultipaneOptions[4],
            "series": seriesStochasticChart
        },
        {
            "chart": chartMultipaneOptions[5],
            "series": seriesMfiChart
        },             
    ], 'multipane')

def create_high_trendline(high_levels):
    if len(high_levels) < 2:
        return None
    sorted_levels = sorted(high_levels, key=lambda x: x['time'])
    if len(sorted_levels) < 2:
        return None
    return {
        "type": "Line",
        "data": [{"time": l['time'], "value": l['value']} for l in sorted_levels],
        "options": {
            "color": "rgba(0, 0, 0, 0.8)",  # 검은색
            "lineWidth": 2,
            "lineStyle": 2,
            "priceLineVisible": False,
            "lastValueVisible": False,
        }
    }

def create_low_trendline(low_levels):
    if len(low_levels) < 2:
        return None
    sorted_levels = sorted(low_levels, key=lambda x: x['time'])
    if len(sorted_levels) < 2:
        return None
    return {
        "type": "Line",
        "data": [{"time": l['time'], "value": l['value']} for l in sorted_levels],
        "options": {
            "color": "rgba(0, 0, 0, 0.8)",  # 검은색
            "lineWidth": 2,
            "lineStyle": 2,
            "priceLineVisible": False,
            "lastValueVisible": False,
        }
    }
        
def find_horizontal_lines(df, lookback_prev=5, lookback_next=5):
    """
    전봉/후봉 기준으로 중심봉이 고점/저점인지 판별하여 수평선 후보 반환
    """
    highs = []
    lows = []

    for i in range(lookback_prev, len(df) - lookback_next):
        window = df.iloc[i - lookback_prev : i + lookback_next + 1]
        center = df.iloc[i]

        if center['high'] == window['high'].max():
            highs.append({
                "time": center['time'],
                "value": center['high'],
                "color": "rgba(255, 0, 0, 0.6)",
                "lineWidth": 1,
                "priceLineVisible": False,
                "lastValueVisible": False
            })

        if center['low'] == window['low'].min():
            lows.append({
                "time": center['time'],
                "value": center['low'],
                "color": "rgba(0, 0, 255, 0.6)",
                "lineWidth": 1,
                "priceLineVisible": False,
                "lastValueVisible": False
            })

    return highs, lows


def create_horizontal_line_segments(lines, candles):
    if not candles:
        return []

    times = [c['time'] for c in candles]
    first_time = times[0]
    last_time = times[-1]

    segments = []
    for line in lines:
        segment = {
            "type": "Line",
            "data": [
                {"time": first_time, "value": line["value"]},
                {"time": last_time, "value": line["value"]}
            ],
            "options": {
                "color": line["color"],
                "lineWidth": line["lineWidth"],
                "priceLineVisible": line["priceLineVisible"],
                "lastValueVisible": line["lastValueVisible"],
            }
        }
        segments.append(segment)
    return segments

def remove_similar_levels(levels, threshold=0.01):
    filtered = []
    for level in levels:
        if all(abs(level['value'] - f['value']) / f['value'] > threshold for f in filtered):
            filtered.append(level)
    return filtered

                        
def login_page():
    """
    로그인 페이지: 사용자 로그인 및 세션 상태 관리
    """
    st.title("🔑 LOGIN PAGE")

    # 사용자 입력 받기
    username = st.text_input("아이디", key="username_input")
    password = st.text_input("비밀번호", type="password", key="password")
    
    # 간단한 사용자 검증 (실제 서비스에서는 DB 연동 필요)
    if st.button("LOGIN"):
        # 로그인 정보 조회
        result = list(UserInfo.scan(
            filter_condition=((UserInfo.id == username) & (UserInfo.password == password))
        ))
        
        if len(result) > 0:
            st.session_state["authenticated"] = True
            st.query_params = {"page" : "main", "login": "true", "username": username}
            st.rerun()  # 로그인 후 페이지 새로고침
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        

def setup_simulation_tab():
    """
    공통적으로 사용할 사이드바 UI를 설정하는 함수
    """
    
    id = "id1"  # 사용자 이름 (고정값)
        
    current_date_kst = datetime.now(pytz.timezone('Asia/Seoul')).date()

    start_date = st.date_input("📅 Start Date", value=date(2023, 1, 1), key=f'start_date')
    end_date = st.date_input("📅 End Date", value=current_date_kst, key=f'end_date')

    st.subheader("💰 매수 금액 설정 방식")

    initial_capital = st.number_input("💰 초기 투자 자본 (KRW)", min_value=0, value=10_000_000, step=1_000_000, key=f"initial_capital_single")

    target_method = st.radio(
        "매수 금액을 어떻게 설정할까요?",
        ["직접 입력", "자본 비율 (%)"],
        index=1,
        horizontal=True,
    )

    if target_method == "직접 입력":
        target_trade_value_krw = st.number_input("🎯 목표 매수 금액 (KRW)", min_value=10000, step=10000, value=1000000, key=f'target_trade_value_krw_single')
        target_trade_value_ratio = None
        min_trade_value = 0
    else:
        target_trade_value_ratio = st.slider("💡 초기 자본 대비 매수 비율 (%)", 1, 100, 25, key=f'target_trade_value_ratio_single') #마우스 커서로 왔다갔다 하는 기능
        min_trade_value = st.number_input("💰 최소 매수금액 (KRW)", min_value=0, value=500000, step=1000000, key=f"min_trade_value_single")
        target_trade_value_krw = None  # 실제 시뮬 루프에서 매일 계산

    result = list(StockSymbol.scan(
        filter_condition=((StockSymbol.type == 'kospi200') | (StockSymbol.type == 'kosdaq150') | (StockSymbol.type == 'NASDAQ') | (StockSymbol.type == 'etf') )
    ))

    # StockSymbol2에서 겹치지 않는 symbol만 추출
    additional_items = [
        item for item in StockSymbol2.scan()
        if item.symbol not in {r.symbol for r in result}
    ]

    # result에 추가
    result.extend(additional_items)
    
    type_order = {
        'kosdaq150': 0,
        'kospi200': 1,
        'kosdaq': 2,
        'NASDAQ': 3,
        'etf': 4
    } #type 순서

    #종목을 type 순서로 정렬한 후 이름순으로 정렬
    sorted_items = sorted(
        result,
        key=lambda x: (
            type_order.get(getattr(x, 'type', ''),99), 
            getattr(x, 'symbol_name', ''))
    )
    

    # Dropdown 메뉴를 통해 데이터 선택
    symbol_options = {
        # "삼성전자": "352820",
        # "대한항공": "003490",
    }

    for stock in sorted_items:
        key = stock.symbol_name  # 'a' 값을 키로
        value = stock.symbol  # 'b' 값을 값으로
        symbol_options[key] = value  # 딕셔너리에 추가
        
    # Dropdown 메뉴를 통해 데이터 선택
    symbol_type = {
        # "352820": "kospi",
        # "003490": "kospi",
    }
    
    for stock in sorted_items:
        key = stock.symbol  # 'a' 값을 키로
        value = stock.type  # 'b' 값을 값으로
        symbol_type[key] = value  # 딕셔너리에 추가
                    
    # interval 설정
    interval_options = {
        "DAY": "day",
        "WEEK": "week",
        "MONTH": "month",
    }

    # 매수/매도 로직 설정
    # JSON 파일 읽기
    file_path = "./dashboard_web/trading_logic.json"
    with open(file_path, "r", encoding="utf-8") as file:
        trading_logic = json.load(file)

    # 사용 예시
    available_buy_logic = trading_logic["available_buy_logic"]
    available_sell_logic = trading_logic["available_sell_logic"]
    available_take_profit_logic = trading_logic["available_take_profit_logic"]
    available_stop_loss_logic = trading_logic["available_stop_loss_logic"]
    
    selected_stock = st.selectbox("Select a Stock", list(symbol_options.keys()))
    selected_interval = st.selectbox("Select Chart Interval", list(interval_options.keys()))
    selected_buy_logic = st.multiselect("Select Buy Logic(s):", list(available_buy_logic.keys()))
    selected_sell_logic = st.multiselect("Select Sell Logic(s):", list(available_sell_logic.keys()))
    
    # 3% 매수 조건 체크박스 (체크하면 'Y', 체크 해제하면 'N')
    buy_condition_enabled = st.checkbox("매수 제약 조건 활성화")  # True / False 반환
    buy_condition_yn = "Y" if buy_condition_enabled else "N"
    
    # 사용자가 직접 매수 퍼센트 (%) 입력 (기본값 3%)
    if buy_condition_yn == 'Y':
        buy_percentage = st.number_input("퍼센트 (%) 입력", min_value=0.0, max_value=100.0, value=3.0, step=0.1)
    else:
        buy_percentage = None
        
    symbol = symbol_options[selected_stock]
    stock_type = symbol_type[symbol]
    print(f"stock_type: {stock_type}")

    interval = interval_options[selected_interval]
    
    selected_buyTrading_logic = [available_buy_logic[logic] for logic in selected_buy_logic] if selected_buy_logic else []
    selected_sellTrading_logic = [available_sell_logic[logic] for logic in selected_sell_logic] if selected_sell_logic else []
    
    take_profit_logic = {
        'name': None,
        'params': {}
    }
    stop_loss_logic = {
        'name': None,
        'params': {}
    }

    #mode
    ohlc_mode_checkbox = st.checkbox("차트 연결 모드")  # True / False 반환
    ohlc_mode = "continuous" if ohlc_mode_checkbox else "default"
        
    use_take_profit = st.checkbox("익절 조건 사용", value=True)
    if use_take_profit:
        selected_take_profit_logic = st.selectbox("익절 방식 선택", list(available_take_profit_logic.keys()))
        take_profit_ratio = st.number_input("익절 기준 (%)", value=5.0, min_value=0.0)

        take_profit_logic_name = available_take_profit_logic[selected_take_profit_logic]
        
        take_profit_logic['name'] = take_profit_logic_name
        take_profit_logic['params']['ratio'] = take_profit_ratio

    use_stop_loss = st.checkbox("손절 조건 사용", value=True)
    if use_stop_loss:
        selected_stop_loss_logic = st.selectbox("손절 방식 선택", list(available_stop_loss_logic.keys()))
        stop_loss_ratio = st.number_input("손절 기준 (%)", value=5.0, min_value=0.0)

        stop_loss_logic_name = available_stop_loss_logic[selected_stop_loss_logic]

        stop_loss_logic['name'] = stop_loss_logic_name
        stop_loss_logic['params']['ratio'] = stop_loss_ratio
        
    #✅ rsi 조건값 입력
    rsi_buy_threshold = st.number_input("📉 RSI 매수 임계값", min_value=0, max_value=100, value=35, step=1)
    rsi_sell_threshold = st.number_input("📈 RSI 매도 임계값", min_value=0, max_value=100, value=70, step=1)
    rsi_period = st.number_input("📈 RSI 기간 설정", min_value=0, max_value=100, value=25, step=1)
    
    # 📌 Streamlit 체크박스 입력
    st.subheader("📊 차트 지표 선택")

    colors = {
        "빨강": "#FF0000",
        "초록": "#00FF00",
        "파랑": "#0000FF",
        "노랑": "#FFFF00",
        "검정": "#000000",
        "흰색": "#FFFFFF",
        "주황": "#FFA500",
        "보라": "#800080",
        "연두": "#ADFF2F",
        "남색": "#000080",
        "하늘색": "#87CEEB",
        "회색": "#808080",
        "갈색": "#A52A2A",
        "분홍": "#FFC0CB",
        "청록": "#008080",
        "올리브": "#808000",
        "라임": "#00FF7F",
        "살구": "#FFB07C",
        "연보라": "#D8BFD8",
        "민트": "#AAF0D1",
    }
    indicators = [
        {
            "type": "ema",
            "period": 5,
            "draw_yn": True,
            "color": "빨강"
        },
        {
            "type": "ema",
            "period": 10,
            "draw_yn": True,
            "color": "초록"
        },
        {
            "type": "ema",
            "period": 20,
            "draw_yn": True,
            "color": "파랑"
        },
        {
            "type": "ema",
            "period": 60,
            "draw_yn": True,
            "color": "보라"
        },
        {
            "type": "ema",
            "period": 120,
            "draw_yn": True,
            "color": "주황"
        },
        {
            "type": "sma",
            "period": 5,
            "draw_yn": False,
            "color": "갈색"
        },
        {
            "type": "sma",
            "period": 20,
            "draw_yn": False,
            "color": "청록"
        },
        {
            "type": "sma",
            "period": 40,
            "draw_yn": False,
            "color": "남색"
        },
        {
            "type": "sma",
            "period": 120,
            "draw_yn": False,
            "color": "올리브"
        },
        {
            "type": "sma",
            "period": 200,
            "draw_yn": False,
            "color": "회색"
        },
    ]

    for idx, indicator in enumerate(indicators):
        if idx == 0:
            st.write("##### EMA")
        elif idx == 5:
            st.write("##### SMA")
        with st.container():
            # 3개의 열로 나누기
            col0, col1, col2, col3 = st.columns([1, 2, 2, 10])
            with col0:
                indicator['draw_yn'] = st.checkbox(f"선택_{idx}", value=indicator['draw_yn'], label_visibility="collapsed")
            # 두 번째 열: 숫자 입력
            with col1:
                indicator['period'] = st.number_input("수량", min_value=0, value=indicator['period'], step=1, key=f"period_{idx}", label_visibility="collapsed")
                indicator['name'] = f"{indicator['type']}_{indicator['period']}"
            # 세 번째 열: 라디오 버튼
            with col2:
                colors_options = list(colors.keys())

                def format_color_label(name):
                    return f"{name}"

                indicator['color'] = st.selectbox("색상 선택", options=colors_options, index=colors_options.index(indicator['color']), format_func=format_color_label, key=f"color_selectbox_{idx}", label_visibility="collapsed")
                indicator['color_hex'] = colors[indicator['color']]
            with col3:
                st.markdown(
                    f"<div style='width:40px;height:40px;background:{indicator['color_hex']};border:0px solid black; margin-top:0px; margin-bottom:0px;'></div>",
                    unsafe_allow_html=True
                )
             
    if st.checkbox("bollinger band", value=True):
        indicators.append({
            'type': "bollinger_band",
            'name': "bollinger band",
            'color_hex': "#000000",
        })
    if st.checkbox("horizontal_high", value=False):
        indicators.append({
            'type': "horizontal_high",
            'name': "horizontal_high",
            'color_hex': "#000000",
        })
    if st.checkbox("horizontal_low", value=False):
        indicators.append({
            'type': "horizontal_low",
            'name': "horizontal_low",
            'color_hex': "#000000",
        })
    if st.checkbox("high_trendline", value=False):
        indicators.append({
            'type': "high_trendline",
            'name': "high_trendline",
            'color_hex': "#000000",
        })
    if st.checkbox("low_trendline", value=False):
        indicators.append({
            'type': "low_trendline",
            'name': "low_trendline",
            'color_hex': "#000000",
        })        
        
    # ✅ 설정 값을 딕셔너리 형태로 반환
    return {
        "id": id,
        "start_date": start_date,
        "end_date": end_date,
        "target_trade_value_krw": target_trade_value_krw,
        "target_trade_value_ratio": target_trade_value_ratio,
        "min_trade_value": min_trade_value,
        "kospi200": symbol_options,
        "symbol": symbol,
        "selected_stock": selected_stock,
        "stock_type" : stock_type,
        "interval": interval,
        "buy_trading_logic": selected_buyTrading_logic,
        "sell_trading_logic": selected_sellTrading_logic,
        "buy_condition_yn": buy_condition_yn,
        "buy_percentage": buy_percentage,
        "ohlc_mode": ohlc_mode,
        "rsi_buy_threshold" : rsi_buy_threshold,
        "rsi_sell_threshold" : rsi_sell_threshold,
        "rsi_period" : rsi_period,
        "indicators" : indicators,
        "initial_capital" : initial_capital,
        "take_profit_logic" : take_profit_logic,
        "stop_loss_logic": stop_loss_logic,
    }

def read_csv_from_presigned_url(presigned_url):

    print(f"presigned_url = {presigned_url}")
    response = requests.get(presigned_url)
    response.raise_for_status()  # 에러 나면 여기서 멈춤
    csv_buffer = StringIO(response.text)
    df = pd.read_csv(csv_buffer)
    return df

def read_json_from_presigned_url(presigned_url):
    print(f"presigned_url = {presigned_url}")
    
    response = requests.get(presigned_url)
    response.raise_for_status()  # 오류 발생 시 예외 발생
    
    # response.text 또는 response.json() 선택 가능
    # 만약 JSON 파일 구조가 DataFrame으로 바로 변환 가능한 형식이면:
    data = response.json()
    
    return data

def format_date_ymd(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    elif isinstance(value, str):
        return value[:10]  # 'YYYY-MM-DD' 형식만 자름
    else:
        return str(value)  # 혹시 모를 예외 처리

            # ✅ 함수: 가상 익절/손절 판단
def simulate_virtual_sell(df, start_idx, buy_price, take_profit_ratio, stop_loss_ratio):
    for i in range(start_idx + 1, len(df)):
        close = df["Close"].iloc[i]
        roi = ((close - buy_price) / buy_price) * 100

        if roi >= take_profit_ratio:
            return "take_profit", roi, df.index[i]
        elif roi <= -stop_loss_ratio:
            return "stop_loss", roi, df.index[i]
    return None, None, None
            

def draw_bulk_simulation_result(assets, results, simulation_settings):

    # debug 용
    # st.json(results, expanded=False)
    
    results_df = pd.DataFrame(results)

    results_df["timestamp"] = pd.to_datetime(results_df["timestamp_str"])
    results_df = results_df.sort_values(by=["timestamp", "symbol"]).reset_index(drop=True)
    results_df["timestamp"] = results_df["timestamp"].dt.strftime("%Y-%m-%d")

    reorder_columns = [
        "timestamp", "symbol", "initial_capital", "portfolio_value", "quantity",
        "realized_pnl", "realized_roi", "unrealized_pnl", "unrealized_roi",
        "total_quantity", "average_price", "take_profit_hit", "stop_loss_hit", "fee_buy", "fee_sell", "tax", "total_costs", "signal_reasons", "total_buy_cost", "buy_signal_info", "ohlc_data_full", "history", "stock_type"
    ]
    results_df = results_df[[col for col in reorder_columns if col in results_df.columns]]

    for col in ["realized_roi", "unrealized_roi"]:
        if col in results_df.columns:
            results_df[col] = results_df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else x)
    

    signal_logs = []
    for row in results:
        raw_reasons = row.get("signal_reasons", [])
        
        # 문자열이면 리스트로 변환
        if isinstance(raw_reasons, str):
            reasons_list = [raw_reasons]
        # 리스트인데 내부에 리스트가 있으면 flatten
        elif isinstance(raw_reasons, list):
            if raw_reasons and isinstance(raw_reasons[0], list):
                reasons_list = [item for sublist in raw_reasons for item in sublist]
            else:
                reasons_list = raw_reasons
        else:
            reasons_list = []

        reasons = ", ".join(map(str, reasons_list))

        if row.get("buy_signal"):
            signal_logs.append({
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "signal": "BUY_SIGNAL",
                "reason": reasons
            })
        if row.get("sell_signal"):
            signal_logs.append({
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "signal": "SELL_SIGNAL",
                "reason": reasons
            })

    # ✅ 시뮬레이션 params
    st.markdown("---")
    st.subheader("📊 시뮬레이션 설정")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("시작 날짜", format_date_ymd(simulation_settings["start_date"]))
        st.metric("종료 날짜", format_date_ymd(simulation_settings["end_date"]))
        st.metric("일자 별", simulation_settings.get("interval") if simulation_settings.get("interval") else "없음")
        st.metric("매수 제약 조건", simulation_settings["buy_condition_yn"] if simulation_settings.get("buy_condition_yn") else "없음")
    with col2:
        st.metric("초기 자본", f"{int(simulation_settings['initial_capital']):,}" if simulation_settings.get("initial_capital") else "없음")
        st.metric("자본 비율", simulation_settings["target_trade_value_ratio"] if simulation_settings.get("target_trade_value_ratio") else "없음")
        st.metric("목표 거래 금액", simulation_settings.get("target_trade_value_krw") if simulation_settings.get("target_trade_value_krw") else "없음")
        st.metric("매수 제약 조건 비율", simulation_settings["buy_percentage"] if simulation_settings.get("buy_percentage") else "없음")
    with col3:
        st.metric("rsi_period", simulation_settings["rsi_period"] if simulation_settings.get("rsi_period") else "없음")
        st.metric("rsi_buy_threshold", simulation_settings["rsi_buy_threshold"] if simulation_settings.get("rsi_buy_threshold") else "없음")
        st.metric("rsi_sell_threshold", simulation_settings["rsi_sell_threshold"] if simulation_settings.get("rsi_sell_threshold") else "없음")
    with col4:
        st.metric("익절 로직", simulation_settings["take_profit_logic"]["name"] if simulation_settings.get("take_profit_logic") else "없음")
        st.metric("익절 비율", simulation_settings["take_profit_logic"]["params"]["ratio"] if simulation_settings.get("take_profit_logic") else "없음")
        st.metric("손절 로직", simulation_settings["stop_loss_logic"]["name"] if simulation_settings.get("stop_loss_logic") else "없음")
        st.metric("손절 비율", simulation_settings["stop_loss_logic"]["params"]["ratio"] if simulation_settings.get("stop_loss_logic") else "없음")

    # 한글 로직 이름 맵핑
    file_path = "./dashboard_web/trading_logic.json"
    with open(file_path, "r", encoding="utf-8") as f:
        trading_logic = json.load(f)

    buy_trading_logic = simulation_settings["buy_trading_logic"]
    sell_trading_logic = simulation_settings["sell_trading_logic"]
    # take_profit_logic = simulation_settings["take_profit_logic"]
    # stop_loss_logic = simulation_settings["stop_loss_logic"]

    # 코드 기준으로 필요한 항목만 필터링
    filtered_buy_logic = {
        k: v for k, v in trading_logic["available_buy_logic"].items() if v in buy_trading_logic
    }
    filtered_sell_logic = {
        k: v for k, v in trading_logic["available_sell_logic"].items() if v in sell_trading_logic
    }

    # 최종 결과
    trading_logic_dict = {
        "buy_trading_logic": filtered_buy_logic,
        "sell_trading_logic": filtered_sell_logic
    }

    st.write("###### 선택한 종목")
    st.json(simulation_settings.get("selected_symbols", []), expanded=False)
    st.write("###### 매수 로직")
    st.json(trading_logic_dict["buy_trading_logic"], expanded=False)
    st.write("###### 매도 로직")
    st.json(trading_logic_dict["sell_trading_logic"], expanded=False)

    ### 시뮬레이션 상세 내용 코드
    results_df = pd.DataFrame(results)

    # 표출하고 싶은 컬럼 필터
    columns_to_show = [
        "timestamp_str", "stock_name", "stock_type", "close_price", "avg_price", "total_quantity", "trade_type",
        "reason", "realized_pnl", "realized_roi", "unrealized_pnl", "unrealized_roi", "krw_balance",
        "buy_logic_reasons", "sell_logic_reasons"
    ]
    columns_rename = {
        "timestamp_str": "날짜",
        "stock_name": "종목명",
        "stock_type": "종목타입",
        "close_price": "종가",
        "avg_price": "평균단가",
        "total_quantity": "보유수량",
        "trade_type": "거래유형",
        "reason": "사유",
        "realized_pnl": "실현손익",
        "realized_roi": "실현수익률(%)",
        "unrealized_pnl": "미실현손익",
        "unrealized_roi": "미실현수익률(%)",
        "krw_balance": "잔고",
        "buy_logic_reasons": "매수사유",
        "sell_logic_reasons": "매도사유"
    }
    # 선택한 컬럼만 DataFrame 생성
    results_df_display = results_df[columns_to_show]
    results_df_display_ko = results_df_display.rename(columns=columns_rename)

    gb = GridOptionsBuilder.from_dataframe(results_df_display_ko)

    int_columns = ["close_price", "avg_price", "total_quantity", "realized_pnl", "unrealized_pnl", "krw_balance"]
    float_columns = ["realized_roi", "unrealized_roi"]

    # 한글 컬럼명 리스트 생성
    columns_to_show_ko = [columns_rename.get(col, col) for col in columns_to_show]
    int_columns_ko = [columns_rename.get(col, col) for col in int_columns]
    float_columns_ko = [columns_rename.get(col, col) for col in float_columns]

    for col in columns_to_show_ko:
        if col in int_columns_ko: # int 표현하고 싶은 컬럼에 대해 format 지정
            gb.configure_column(
                col,
                filter=True,  # 문자 필터 활성화
                type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                valueFormatter="x == null ? '' : x.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})" # 천 단위로 표시 및 소숫점 0자리 표현
            )
    
        elif col in float_columns_ko: # 소숫점 한자리로 표현하고 싶은 컬럼에 대해 format 지정
            gb.configure_column(
                col,
                filter=True,  # 문자 필터 활성화
                type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
                valueFormatter="x == null ? '' : x.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2})" # 천 단위로 표시 및 소숫점 2자리 표현
            )
        else:
            gb.configure_column(
                col,
                filter=True,  # 문자 필터 활성화
                type=["agTextColumnFilter"]
            )

    grid_options = gb.build()
    grid_options["autoSizeStrategy"] = {
        "type": "fitGridWidth",  # 또는 "expand", "off" 등
        "defaultMinWidth": 100    # 최소 너비(px) 지정 가능
    }

    st.markdown("---")
    st.subheader("📋 시뮬레이션 상세 내용")
    # AgGrid로 테이블 표시

    grid_response = AgGrid(
        results_df_display_ko,
        key=f'bulk_simulation_result_detail_{random.random()}',
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        sortable=True,  # 정렬 가능
        filter=True,    # 필터링 가능
        resizable=True, # 크기 조절 가능
        theme='streamlit',   # 테마 변경 가능 ('light', 'dark', 'blue', 등)
    )

    st.markdown("---")
    st.subheader("📊 전체 요약 통계")

    krw_balance = assets['krw_balance']
    total_realized_pnl = results_df["realized_pnl"].sum()

    # unrealized_pnl 연산 (종목 합)
    total_unrealized_pnl = 0
    total_market_value = 0
    
    for holding in assets['account_holdings']:
        unrealized_pnl = (holding['close_price'] - holding['avg_price']) * holding['total_quantity']
        total_unrealized_pnl += unrealized_pnl

        market_value = holding['close_price'] * holding['total_quantity']
        total_market_value += market_value

    total_buy_count = (results_df["trade_type"] == "BUY").sum()
    total_sell_count = (results_df["trade_type"] == "SELL").sum()

    total_buy_signal_count = results_df["buy_logic_reasons"].apply(lambda x: bool(x) and x != "[]").sum()
    total_sell_signal_count = results_df["sell_logic_reasons"].apply(lambda x: bool(x) and x != "[]").sum()

    initial_capital = assets["initial_capital"]
    if initial_capital and initial_capital > 0:
        avg_realized_roi_per_capital = (total_realized_pnl / initial_capital) * 100
        avg_total_roi_per_capital = ((total_realized_pnl + total_unrealized_pnl) / initial_capital) * 100
    else:
        avg_realized_roi_per_capital = None
        avg_total_roi_per_capital = None

    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 총 자산", f"{(krw_balance+total_market_value):,.0f} KRW")
        st.metric("💰 총 실현 손익", f"{total_realized_pnl:,.0f} KRW")
        st.metric("📈 총 미실현 손익", f"{total_unrealized_pnl:,.0f} KRW")
    with col2:
        st.metric("💰 현재 예수금", f"{krw_balance:,.0f} KRW")
        st.metric("📊 초기 자본 대비 평균 실현 손익률", f"{avg_realized_roi_per_capital:.2f}%" if avg_realized_roi_per_capital is not None else "N/A")
        st.metric("📉 초기 자본 대비 평균 총 손익률", f"{avg_total_roi_per_capital:.2f}%" if avg_total_roi_per_capital is not None else "N/A")

    # ✅ 세부 통계 추가
    total_take_profit = results_df["take_profit_hit"].sum() if "take_profit_hit" in results_df.columns else 0
    total_stop_loss = results_df["stop_loss_hit"].sum() if "stop_loss_hit" in results_df.columns else 0

    tp_pnl = results_df[results_df["take_profit_hit"] == True]["realized_pnl"].sum() if "take_profit_hit" in results_df.columns else 0
    sl_pnl = results_df[results_df["stop_loss_hit"] == True]["realized_pnl"].sum() if "stop_loss_hit" in results_df.columns else 0
    logic_sell_pnl = results_df[
        (results_df["trade_type"] == "SELL") &
        (results_df["take_profit_hit"] == False) &
        (results_df["stop_loss_hit"] == False)
    ]["realized_pnl"].sum()
    
    total_fee = results_df["fee"].sum()
    total_tax = results_df["tax"].sum()

    roi_per_total_buy_cost = ((total_realized_pnl + total_unrealized_pnl) / results_df['total_buy_cost'].sum()) * 100
    total_take_profit_per_total_sell_count = (total_take_profit / total_sell_count) * 100
    st.markdown("---")
    st.subheader("📊 추가 세부 요약 통계")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("🟢 총 매수 횟수", f"{total_buy_count}")
        st.metric("🔴 총 매도 횟수", f"{total_sell_count}")
        st.metric("✅ 익절 횟수", f"{total_take_profit}")
        st.metric("⚠️ 손절 횟수", f"{total_stop_loss}")
        st.metric("🟢 총 매수 신호 횟수", f"{total_buy_signal_count}")
        st.metric("🔴 총 매도 신호 횟수", f"{total_sell_signal_count}")

    with col2:
        st.metric("💸 익절로 인한 손익", f"{tp_pnl:,.0f} KRW")
        st.metric("💥 손절로 인한 손익", f"{sl_pnl:,.0f} KRW")
        st.metric("🔄 로직 매도로 인한 손익", f"{logic_sell_pnl:,.0f} KRW")
        st.metric("🔄 총 매수 금액 대비 수익률", f"{roi_per_total_buy_cost:.2f}%")
        st.metric("💸 매도 횟수 대비 익절률", f"{total_take_profit_per_total_sell_count:.2f}%")
        st.metric("🧾 총 수수료", f"{total_fee:,.0f} KRW")
        st.metric("📜 총 거래세", f"{total_tax:,.0f} KRW")

    # ✅ 거래 여부와 무관한 신호 발생 통계 요약
    if signal_logs:
        df_signals_stat = pd.DataFrame(signal_logs)
        total_buy_signals = len(df_signals_stat[df_signals_stat["signal"] == "BUY_SIGNAL"])
        total_sell_signals = len(df_signals_stat[df_signals_stat["signal"] == "SELL_SIGNAL"])

        # 익절/손절은 거래가 발생했을 때만 측정 가능 → 거래 결과로부터
        total_tp_from_trades = results_df["take_profit_hit"].sum() if "take_profit_hit" in results_df.columns else 0
        total_sl_from_trades = results_df["stop_loss_hit"].sum() if "stop_loss_hit" in results_df.columns else 0

        take_profit_ratio_per_sell_signal = (
            (total_tp_from_trades / total_sell_signals) * 100 if total_sell_signals > 0 else None
        )

        st.markdown("---")
        st.subheader("📌 매매 신호 통계 요약 (거래 여부 무관)")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📍 총 매수 신호", total_buy_signals)
            st.metric("📍 총 매도 신호", total_sell_signals)
        with col2:
            st.metric("✅ 익절 발생 (총)", total_tp_from_trades)
            st.metric("⚠️ 손절 발생 (총)", total_sl_from_trades)
            st.metric("📈 매도 신호 대비 익절률", f"{take_profit_ratio_per_sell_signal:.2f}%" if take_profit_ratio_per_sell_signal is not None else "N/A")
            

    #         # st.markdown("---")
    #         # st.subheader("🛠️ 가상 익절/손절 판단 디버깅")

    #         # debug_rows = 0
    #         # for row in results:
    #         #     signal_info = row.get("buy_signal_info")
    #         #     df_full = row.get("ohlc_data_full")

    #         #     if signal_info:
    #         #         st.write(
    #         #         f"📘 BUY_SIGNAL 발생: {row['symbol']} on {signal_info['date'].strftime('%Y-%m-%d')} @ {signal_info['price']}"
    #         #     )
    #         #     else:
    #         #         st.write(f"🚫 No buy_signal_info for {row['symbol']}")
    #         #         continue

    #         #     if df_full is None:
    #         #         st.write(f"❌ {row['symbol']} → ohlc_data_full 없음")
    #         #         continue
    #         #     st.write(f"📂 df_full type: {type(df_full)}")
    #         #     st.write(f"🧩 df_full.index: {df_full.index if hasattr(df_full, 'index') else '❌ index 없음'}")

    #         #     try:
    #         #         start_idx = df_full.index.get_loc(pd.Timestamp(signal_info["date"]))
    #         #     except KeyError:
    #         #         st.write(f"❌ {row['symbol']} → Index에서 {signal_info['date']} 못 찾음")
    #         #         continue

    #         #     outcome, roi, outcome_date = simulate_virtual_sell(
    #         #         df_full, start_idx, signal_info["price"],
    #         #         take_profit_ratio=simulation_settings["take_profit_ratio"],
    #         #         stop_loss_ratio=simulation_settings["stop_loss_ratio"]
    #         #     )

    #             # debug_rows += 1
    #             # if debug_rows >= 5:
    #             #     break  # 디버깅 출력 너무 많으면 중단
    
    #             # ✅ 거래 여부 무관, 신호 발생 기준 가상 익절/손절 내역 추적
    #             # virtual_hits = []

    #             # for row in results:
    #             #     signal_info = row.get("buy_signal_info")
    #             #     df_full = row.get("ohlc_data_full")

    #             #     if signal_info is None:
    #             #         st.write(f"🚫 No buy_signal_info for {row['symbol']}")
    #             #         continue
    #             #     if df_full is None or not isinstance(df_full, pd.DataFrame):
    #             #         st.write(f"❌ ohlc_data_full이 잘못되었거나 없음: {row['symbol']}")
    #             #         continue

    #             #     # ✅ 안전하게 날짜 변환
    #             #     try:
    #             #         signal_dt = pd.to_datetime(signal_info["date"]).normalize()
    #             #     except Exception as e:
    #             #         st.write(f"❌ 날짜 변환 실패: {e}")
    #             #         continue

    #             #     try:
    #             #         df_full.index = pd.to_datetime(df_full.index).normalize()
    #             #         start_idx = df_full.index.get_loc(signal_dt)
    #             #     except KeyError:
    #             #         st.write(f"❌ {row['symbol']} → df_full.index에 {signal_dt} 없음")
    #             #         continue
    #             #     except Exception as e:
    #             #         st.write(f"❌ index 오류: {e}")
    #             #         continue

    #             #     outcome, roi, outcome_date = simulate_virtual_sell(
    #             #         df_full, start_idx, signal_info["price"],
    #             #         take_profit_ratio=simulation_settings["take_profit_ratio"],
    #             #         stop_loss_ratio=simulation_settings["stop_loss_ratio"]
    #             #     )

    #             #     if outcome:
    #             #         virtual_hits.append({
    #             #             "symbol": row["symbol"],
    #             #             "buy_date": signal_dt.strftime("%Y-%m-%d"),
    #             #             "outcome_date": outcome_date.strftime("%Y-%m-%d"),
    #             #             "type": "✅ 익절" if outcome == "take_profit" else "⚠️ 손절",
    #             #             "roi": f"{roi:.2f}%",
    #             #             "reason": "가상 매수 후 조건 충족"
    #             #         })

    #             # if virtual_hits:
    #             #     df_virtual = pd.DataFrame(virtual_hits)
    #             #     st.markdown("---")
    #             #     st.subheader("🧪 거래 여부 무관: 가상 매수 기준 익절/손절 내역")
    #             #     st.dataframe(df_virtual, use_container_width=True)
    #             # else:
    #             #     st.info("📭 가상 익절/손절 내역 없음")
                                    
    #     if failed_stocks:
    #         st.warning(f"⚠️ 시뮬레이션 실패 종목 ({len(failed_stocks)}개): {', '.join(sorted(failed_stocks))}")
    # else:
    #     st.warning("⚠️ 시뮬레이션 결과가 없습니다.")

def main():
    
    st.set_page_config(layout="wide")
    col1, col2, col3 = st.columns([6, 1, 1])

    with col3:
        if st.button("LOGOUT"):
            st.session_state["authenticated"] = False
            st.query_params = {"page" : "login", "login": "false", "username": ""}
            st.rerun()  # 로그아웃 후 페이지 새로고침
            
    st.title("FSTS SIMULATION")
    
    # 탭 생성
    tabs = st.tabs(["🏠 Bot Transaction History", "📈 Simulation Graph", "📊 KOSPI200 Simulation", "📊 Simulation Result", "📈Auto Trading Bot Balance", "🏆Ranking", "Setting", "Today's Updown"])

    # 각 탭의 내용 구성
    with tabs[0]:
        st.header("🏠  Bot Transaction History")
        
        data = {
            "Trading Bot Name": [],
            "Trading Logic": [],
            "Trade Date": [],
            "Symbol Name": [],
            "Symbol": [],
            "Position": [],
            "Price": [],
            "Quantity": []
        }

        result = list(TradingHistory.scan())

        sorted_result = sorted(
            result,
            key=lambda x: (x.trading_logic, -x.trade_date, x.symbol_name) #trade_date 최신 순
        )
        
        for row in sorted_result:
            # 초 단위로 변환
            sec_timestamp = row.trade_date / 1000
            # 포맷 변환
            formatted_trade_date = datetime.fromtimestamp(sec_timestamp).strftime('%Y-%m-%d %H:%M:%S')

            data["Trading Bot Name"].append(row.trading_bot_name)
            data["Trading Logic"].append(row.trading_logic)
            data["Trade Date"].append(formatted_trade_date)
            data["Symbol Name"].append(row.symbol_name)
            data["Symbol"].append(row.symbol)
            data["Position"].append(row.position)
            data["Price"].append(f"{row.price:,.0f}")
            data["Quantity"].append(f"{row.quantity:,.0f}")

        df = pd.DataFrame(data)
        
        # AgGrid로 테이블 표시
        AgGrid(
            df,
            editable=True,  # 셀 편집 가능
            sortable=True,  # 정렬 가능
            filter=True,    # 필터링 가능
            resizable=True, # 크기 조절 가능
            theme='streamlit',   # 테마 변경 가능 ('light', 'dark', 'blue', 등)
            fit_columns_on_grid_load=True  # 열 너비 자동 조정
        )
    
    with tabs[1]:
        st.header("📈 종목 시뮬레이션")

        simulation_settings = setup_simulation_tab()
        
        if st.button("개별 종목 시뮬레이션 실행", key = 'simulation_button'):
            
            with st.container():
                st.write(f"📊 {simulation_settings['selected_stock']} 시뮬레이션 실행 중...")
                
                url = f"{backend_base_url}/stock/simulate/single"

                print(f'url = {url}')

                payload = {
                    "user_id": simulation_settings["id"],
                    "symbol": simulation_settings["symbol"],
                    "stock_name": simulation_settings["selected_stock"],
                    "stock_type": simulation_settings['stock_type'],
                    "start_date": simulation_settings["start_date"].isoformat(),
                    "end_date": simulation_settings["end_date"].isoformat(),
                    "target_trade_value_krw": simulation_settings["target_trade_value_krw"],
                    "target_trade_value_ratio": simulation_settings['target_trade_value_ratio'],
                    "min_trade_value": simulation_settings["min_trade_value"],
                    "buy_trading_logic": simulation_settings["buy_trading_logic"],
                    "sell_trading_logic": simulation_settings["sell_trading_logic"],
                    "interval": simulation_settings["interval"],
                    "buy_percentage": simulation_settings["buy_percentage"],
                    "ohlc_mode": simulation_settings["ohlc_mode"],
                    "rsi_buy_threshold": simulation_settings["rsi_buy_threshold"],
                    "rsi_sell_threshold": simulation_settings["rsi_sell_threshold"],
                    "rsi_period": simulation_settings["rsi_period"],
                    "initial_capital": simulation_settings["initial_capital"],
                    "take_profit_logic": simulation_settings["take_profit_logic"],
                    "stop_loss_logic": simulation_settings["stop_loss_logic"],
                    "indicators": simulation_settings['indicators'],
                }

                response = requests.post(url, json=payload).json()
                print(response)

                json_url = response['json_url']
                json_data = read_json_from_presigned_url(json_url)
                data_url = json_data['data_url']
                data_df = read_csv_from_presigned_url(data_url)
                simulation_histories = json_data['simulation_histories']
                assets = json_data['assets']

                # ✅ 상태 저장
                st.session_state["simulation_result"] = {
                    "data_df": data_df,
                    "assets": assets,
                    "simulation_histories": simulation_histories,
                    "indicators": simulation_settings['indicators'],
                    "selected_stock": simulation_settings["selected_stock"]
                }

        # ✅ 이전 시뮬 결과가 있는 경우 표시
        if "simulation_result" in st.session_state:
            result = st.session_state["simulation_result"]
            data_df = result["data_df"]
            assets = result["assets"]
            simulation_histories = result["simulation_histories"]
            indicators = result["indicators"]

            # CSV 다운로드 버튼
            # st.subheader("📥 데이터 다운로드")
            # csv_buffer = io.StringIO()
            # pd.DataFrame(trade_reasons).to_csv(csv_buffer, index=False)
            # st.download_button(
            #     label="📄 CSV 파일 다운로드",
            #     data=csv_buffer.getvalue(),
            #     file_name="trade_reasons.csv",
            #     mime="text/csv"
            # )
            #     simulation_result = {
            #         "data_df": data_df,
            #         "trading_history": trading_history,
            #         "trade_reasons": trade_reasons
            #     }
    
            # result = simulation_result
            # data_df = result["data_df"]
            # trading_history = result["trading_history"]
            # trade_reasons = result["trade_reasons"]
            
            # # CSV 다운로드 버튼 - trade_reasons DataFrame 생성 후 다운로드
            # if trade_reasons:
            #     df_trade = pd.DataFrame(trade_reasons)
            # else:
            #     st.warning("🚨 거래 내역이 없습니다.")
            #     df_trade = pd.DataFrame()
            
            # st.subheader("📥 데이터 다운로드")
            # csv_buffer = io.StringIO()
            # df_trade.to_csv(csv_buffer, index=False)
            # st.download_button(
            #     label="📄 CSV 파일 다운로드",
            #     data=csv_buffer.getvalue(),
            #     file_name="trade_reasons.csv",
            #     mime="text/csv"
            # )
            
            # TradingView 차트 그리기
            draw_lightweight_chart(data_df, assets, indicators)
            
            # 결과 result
            draw_bulk_simulation_result(assets, simulation_histories, simulation_settings)

        else:
            st.info("먼저 시뮬레이션을 실행해주세요.")
            
    with tabs[2]:
        
        id = "id1"  # 사용자 이름 (고정값)
        
        current_date_kst = datetime.now(pytz.timezone('Asia/Seoul')).date()

        start_date = st.date_input("📅 Start Date", value=date(2023, 1, 1))
        end_date = st.date_input("📅 End Date", value=current_date_kst)
        
        st.subheader("💰 매수 금액 설정 방식")

        initial_capital = st.number_input("💰 초기 투자 자본 (KRW)", min_value=0, value=10_000_000, step=100_000_000, key=f"initial_capital")

        target_method = st.radio(
            "매수 금액을 어떻게 설정할까요?",
            ["직접 입력", "자본 비율 (%)"],
            index=1,
            horizontal=True,
            key=f'target_method'
        )

        if target_method == "직접 입력":
            target_trade_value_krw = st.number_input("🎯 목표 매수 금액 (KRW)", min_value=10000, step=10000, value=1000000, key=f'target_trade_value_krw')
            target_trade_value_ratio = None
            min_trade_value = 0
        else:
            target_trade_value_ratio = st.slider("💡 초기 자본 대비 매수 비율 (%)", 1, 100, 25, key=f'target_trade_value_ratio') #마우스 커서로 왔다갔다 하는 기능
            min_trade_value = st.number_input("💰 최소 매수금액 (KRW)", min_value=0, value=500000, step=1000000, key=f"min_trade_value")
            target_trade_value_krw = None  # 실제 시뮬 루프에서 매일 계산
    
        # ✅ 종목 불러오기
        kospi_kosdaq150 = list(StockSymbol.scan(
            filter_condition=((StockSymbol.type == 'kospi200') | (StockSymbol.type == 'kosdaq150'))
        ))
        kosdaq_all_result = list(StockSymbol2.scan(
            filter_condition=(StockSymbol2.type == 'kosdaq')
        ))
        sorted_items = sorted(
            kospi_kosdaq150,
            key=lambda x: (
                {'kospi200': 1, 'kosdaq150': 2}.get(getattr(x, 'type', ''), 99),
                getattr(x, 'symbol_name', ''))
        )

        # ✅ 종목 분류
        kospi200_items = [row for row in sorted_items if getattr(row, 'type', '') == 'kospi200']
        kosdaq150_items = [row for row in sorted_items if getattr(row, 'type', '') == 'kosdaq150']
        kosdaq_items = [row for row in kosdaq_all_result if getattr(row, 'type', '') == 'kosdaq']

        kospi200_names = [row.symbol_name for row in kospi200_items]
        kosdaq150_names = [row.symbol_name for row in kosdaq150_items]
        kosdaq_all_names = [row.symbol_name for row in kosdaq_items]
        all_symbol_names = list(set(row.symbol_name for row in (sorted_items + kosdaq_items)))

        # ✅ symbol + type mapping
        symbol_options_main = {row.symbol_name: row.symbol for row in sorted_items}
        symbol_options_kosdaq = {row.symbol_name: row.symbol for row in kosdaq_items}
        symbol_options = {**symbol_options_main, **symbol_options_kosdaq}
        
        # ✅ symbol + type 매핑 (symbol 기준)
        symbol_type_map_main = {
            row.symbol: getattr(row, "type", "unknown")
            for row in sorted_items
        }

        # ✅ 덮어쓰기 없이 병합
        for row in kosdaq_items:
            symbol = row.symbol
            if symbol not in symbol_type_map_main:
                symbol_type_map_main[symbol] = getattr(row, "type", "unknown")

        # ✅ 병합
        symbol_type_map = symbol_type_map_main # 	{symbol: type}

        # ✅ 세션 상태 초기화
        if "selected_stocks" not in st.session_state:
            st.session_state["selected_stocks"] = []

        # ✅ 버튼 UI
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 4])
        

        with col1:
            if st.button("✅ 전체 선택", key="btn_all2"):
                st.session_state["selected_stocks"] = list(set(
                    st.session_state["selected_stocks"] + all_symbol_names
                ))

        with col2:
            if st.button("🏦 코스피 200 추가", key="btn_kospi2"):
                st.session_state["selected_stocks"] = list(set(
                    st.session_state["selected_stocks"] + kospi200_names
                ))

        with col3:
            if st.button("📈 코스닥 150 추가", key="btn_kosdaq150_2"):
                st.session_state["selected_stocks"] = list(set(
                    st.session_state["selected_stocks"] + kosdaq150_names
                ))

        with col4:
            if st.button("📊 코스닥 전체 추가", key="btn_kosdaq_all2"):
                st.session_state["selected_stocks"] = list(set(
                    st.session_state["selected_stocks"] + kosdaq_all_names
                ))

        with col5:
            if st.button("❌ 선택 해제", key="btn_clear2"):
                st.session_state["selected_stocks"] = []

        # ✅ 세션 상태에 저장된 값 중, 현재 옵션에 존재하는 것만 유지
        if "selected_stocks" in st.session_state:
            st.session_state["selected_stocks"] = [
                s for s in st.session_state["selected_stocks"] if s in symbol_options
            ]

        # ✅ 선택 수 표시
        st.markdown(f"🔎 **선택된 종목 수: {len(st.session_state["selected_stocks"])} 종목**")
                    
        # ✅ 사용자가 원하는 종목 선택 (다중 선택 가능)
        selected_stocks = st.multiselect("📌 원하는 종목 선택", all_symbol_names, key="selected_stocks")
        selected_symbols = {stock: symbol_options[stock] for stock in selected_stocks}
        stock_type = symbol_type_map

        # ✅ 차트 간격 (interval) 설정
        interval_options = {"DAY": "day", "WEEK": "week", "MONTH": "month"}
        selected_interval = st.selectbox("⏳ 차트 간격 선택", list(interval_options.keys()), key="selected_interval")
        interval = interval_options[selected_interval]

        # ✅ 매수/매도 로직 설정
        file_path = "./dashboard_web/trading_logic.json"
        with open(file_path, "r", encoding="utf-8") as file:
            trading_logic = json.load(file)

        available_buy_logic = trading_logic["available_buy_logic"]
        available_sell_logic = trading_logic["available_sell_logic"]
        available_take_profit_logic = trading_logic["available_take_profit_logic"]
        available_stop_loss_logic = trading_logic["available_stop_loss_logic"]

        # ✅ 매수/매도 전략 선택
        selected_buy_logic = st.multiselect("📈 매수 로직 선택", list(available_buy_logic.keys()), key="selected_buy_logic")
        selected_sell_logic = st.multiselect("📉 매도 로직 선택", list(available_sell_logic.keys()), key="selected_sell_logic")

        selected_buyTrading_logic = [available_buy_logic[logic] for logic in selected_buy_logic] if selected_buy_logic else []
        selected_sellTrading_logic = [available_sell_logic[logic] for logic in selected_sell_logic] if selected_sell_logic else []

        # ✅ 3% 매수 조건 체크박스
        buy_condition_yn = st.checkbox("💰 매수 제약 조건 활성화", key="buy_condition_enabled")

        buy_percentage = None
        # ✅ 매수 퍼센트 입력
        if buy_condition_yn:
            buy_percentage = st.number_input("💵 퍼센트 (%) 입력", min_value=0.0, max_value=100.0, value=3.0, step=0.1, key="buy_percentage")
        
        # 익절/손절 세팅
        take_profit_logic = {
            'name': None,
            'params': {}
        }
        stop_loss_logic = {
            'name': None,
            'params': {}
        }
        
        use_take_profit = st.checkbox("익절 조건 사용", value=True, key="use_take_profit")
        if use_take_profit:
            selected_take_profit_logic = st.selectbox("익절 방식 선택", list(available_take_profit_logic.keys()), key="selected_take_profit_logic")
            take_profit_ratio = st.number_input("익절 기준 (%)", value=5.0, min_value=0.0, key="take_profit_ratio")

            take_profit_logic_name = available_take_profit_logic[selected_take_profit_logic]
            
            take_profit_logic['name'] = take_profit_logic_name
            take_profit_logic['params']['ratio'] = take_profit_ratio

        use_stop_loss = st.checkbox("손절 조건 사용", value=True, key="use_stop_loss")
        if use_stop_loss:
            selected_stop_loss_logic = st.selectbox("손절 방식 선택", list(available_stop_loss_logic.keys()), key="selected_stop_loss_logic")
            stop_loss_ratio = st.number_input("손절 기준 (%)", value=5.0, min_value=0.0, key="stop_loss_ratio")

            stop_loss_logic_name = available_stop_loss_logic[selected_stop_loss_logic]

            stop_loss_logic['name'] = stop_loss_logic_name
            stop_loss_logic['params']['ratio'] = stop_loss_ratio     

        #✅ rsi 조건값 입력
        st.subheader("🎯 RSI 조건값 설정")
        rsi_buy_threshold = st.number_input("📉 RSI 매수 임계값", min_value=0, max_value=100, value=35, step=1, key = 'rsi_buy_threshold')
        rsi_sell_threshold = st.number_input("📈 RSI 매도 임계값", min_value=0, max_value=100, value=70, step=1, key = 'rsi_sell_threshold')
        rsi_period = st.number_input("📈 RSI 기간 설정", min_value=0, max_value=100, value=25, step=1, key = 'rsi_period')

        # 시뮬레이션 polling request 여부 확인
        polling_request = False

        if st.button("✅ 시뮬레이션 전체 실행"):
            
            # 설정 저장
            st.session_state["my_page_settings"] = {
                "id": id,
                "start_date": start_date,
                "end_date": end_date,
                "target_trade_value_krw": target_trade_value_krw,
                "target_trade_value_ratio": target_trade_value_ratio,
                "min_trade_value": min_trade_value,
                "selected_stocks": selected_stocks, #이름만
                "selected_symbols": selected_symbols, #이름+코드(key,value)
                "stock_type": stock_type,
                "interval": interval,
                "buy_trading_logic": selected_buyTrading_logic,
                "sell_trading_logic": selected_sellTrading_logic,
                "buy_condition_yn": buy_condition_yn,
                "buy_percentage": buy_percentage,
                "initial_capital": initial_capital,
                "rsi_buy_threshold" : rsi_buy_threshold,
                "rsi_sell_threshold" : rsi_sell_threshold,
                "rsi_period" : rsi_period,
                "take_profit_logic": take_profit_logic,
                "stop_loss_logic": stop_loss_logic,
            }

            # ✅ 저장된 설정 확인
            if "my_page_settings" in st.session_state:
                st.subheader("📌 저장된 설정값")
                st.json(st.session_state["my_page_settings"], expanded=False)

            with st.spinner("📈 전체 종목 OHLC 및 지표 계산 중..."):
                
                simulation_settings = st.session_state["my_page_settings"]

                url = f"{backend_base_url}/stock/simulate/bulk"

                payload = {
                    "user_id": simulation_settings['id'],
                    "start_date": simulation_settings['start_date'].isoformat(),
                    "end_date": simulation_settings['end_date'].isoformat(),
                    "target_trade_value_krw": simulation_settings['target_trade_value_krw'],
                    "target_trade_value_ratio": simulation_settings['target_trade_value_ratio'],
                    "min_trade_value": simulation_settings['min_trade_value'],
                    "selected_stocks": simulation_settings['selected_stocks'],
                    "selected_symbols": simulation_settings['selected_symbols'],
                    "stock_type": simulation_settings['stock_type'],
                    "interval": simulation_settings['interval'],
                    "buy_trading_logic": simulation_settings['buy_trading_logic'],
                    "sell_trading_logic": simulation_settings['sell_trading_logic'],
                    "buy_condition_yn": simulation_settings['buy_condition_yn'],
                    "buy_percentage": simulation_settings['buy_percentage'],
                    "initial_capital": simulation_settings['initial_capital'],
                    "rsi_buy_threshold": simulation_settings['rsi_buy_threshold'],
                    "rsi_sell_threshold": simulation_settings['rsi_sell_threshold'],
                    "rsi_period": simulation_settings['rsi_period'],
                    "take_profit_logic": simulation_settings['take_profit_logic'],
                    "stop_loss_logic": simulation_settings['stop_loss_logic'],
                }

                response = requests.post(url, json=payload).json()
                simulation_id = None
                simulation_id = response['simulation_id']

                if simulation_id is not None:
                    st.success(f"시뮬레이션 요청 성공! simulation id : {simulation_id}")
                else:
                    st.warning("⚠️ 시뮬레이션 요청에 실패했습니다.")
                get_simulation_result_url = f"{backend_base_url}/stock/simulate/bulk/result"
                result_presigned_url = None

                # 프로그레스 바 초기화
                progress_bar = st.progress(0)
                progress_text = st.empty()  # 숫자 출력을 위한 공간
                
                # polling 으로 현재 상태 확인
                while True:
                    params={"simulation_id": simulation_id}
                    response = requests.get(get_simulation_result_url, params=params).json()
                    print(response)

                    total_task_cnt = response["total_task_cnt"]
                    completed_task_cnt = response["completed_task_cnt"]

                    if total_task_cnt == 0:
                        total_task_cnt = 10000 # 임시

                    progress_bar.progress(completed_task_cnt / total_task_cnt)
                    progress_text.text(f"{completed_task_cnt} / {total_task_cnt} 완료")

                    if response["status"] == "completed":
                        result_presigned_url = response["result_presigned_url"]
                        break

                    time.sleep(5)

                st.success("모든 작업 완료!")
                
                json_data = read_json_from_presigned_url(result_presigned_url)

                assets = json_data['assets']
                results = json_data['simulation_histories']
                failed_stocks = json_data['failed_stocks']

                draw_bulk_simulation_result(assets, results, simulation_settings)
    
    with tabs[3]:
        st.header("🏠 Simulation Result")

        data = {
            "simulation_id": [],
            "created_at_dt": [],
            "completed_task_cnt": [],
            "total_task_cnt": [],
            "trigger_type": [],
            "trigger_user": [],
            "status": [],
            "description": []
        }

        result = list(SimulationHistory.scan())

        sorted_result = sorted(
            result,
            key=lambda x: (-x.created_at) #trade_date 최신 순
        )
        
        for row in sorted_result:
            data["simulation_id"].append(row.simulation_id)
            data["created_at_dt"].append(row.created_at_dt)
            data["completed_task_cnt"].append(row.completed_task_cnt)
            data["total_task_cnt"].append(row.total_task_cnt)
            data["trigger_type"].append(row.trigger_type)
            data["trigger_user"].append(row.trigger_user)
            data["status"].append(row.status)
            data["description"].append(row.description)

        df = pd.DataFrame(data)
        
        # Grid 설정
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_selection('single')  # ✅ 한 행만 선택
        grid_options = gb.build()

        selected_rows = None
        selected_grid_row = None

        # AgGrid로 테이블 표시
        grid_response = AgGrid(
            df,
            key='bulk_simulation_result',
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            sortable=True,  # 정렬 가능
            filter=True,    # 필터링 가능
            resizable=True, # 크기 조절 가능
            theme='streamlit',   # 테마 변경 가능 ('light', 'dark', 'blue', 등)
            fit_columns_on_grid_load=True  # 열 너비 자동 조정
        )

        selected_rows = grid_response["selected_rows"]

        if selected_rows is not None:
            selected_grid_row = grid_response["selected_rows"].iloc[0]
            simulation_id = selected_grid_row["simulation_id"]

            get_simulation_result_url = f"{backend_base_url}/stock/simulate/bulk/result"
            result_presigned_url = None

            params={"simulation_id": simulation_id}
            response = requests.get(get_simulation_result_url, params=params).json()

            if response["status"] == "completed":
                params_presigned_url = response["params_presigned_url"]
                result_presigned_url = response["result_presigned_url"]

                simulation_settings = read_json_from_presigned_url(params_presigned_url)
                result_json_data = read_json_from_presigned_url(result_presigned_url)

                assets = result_json_data['assets']
                simulation_histories = result_json_data['simulation_histories']
                failed_stocks = result_json_data['failed_stocks']
                                
                draw_bulk_simulation_result(assets, simulation_histories, simulation_settings)
            
    with tabs[4]:
        st.header("🏠 Auto Trading Bot Balance")
        
        data = {
            "Trading Bot Name": [],
            "Symbol Name": [],
            "Symbol": [],
            "Avg Price": [],
            "Profit": [],
            "Profit Rate": [],
            "Quantity": [],
            "Market": []
        }

        auto_trading_balance = list(AutoTradingBalance.scan())

        # sorted_result = sorted(
        #     result,
        #     key=lambda x: (x.trading_logic, -x.trade_date, x.symbol_name) #trade_date 최신 순
        # )
        
        # for row in sorted_result:
        #     # 초 단위로 변환
        #     sec_timestamp = row.trade_date / 1000
        #     # 포맷 변환
        #     formatted_trade_date = datetime.fromtimestamp(sec_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        for balance in auto_trading_balance:
            data["Trading Bot Name"].append(balance.trading_bot_name)
            data["Symbol Name"].append(balance.symbol_name)
            data["Symbol"].append(balance.symbol)
            data["Avg Price"].append(balance.avg_price)
            data["Profit"].append(balance.profit)
            data["Profit Rate"].append(balance.profit_rate)
            data["Quantity"].append(balance.quantity)
            data["Market"].append(balance.market)

        df = pd.DataFrame(data)
        
        # AgGrid로 테이블 표시
        AgGrid(
            df,
            editable=True,
            sortable=True,
            filter=True,
            resizable=True,
            theme='streamlit',
            fit_columns_on_grid_load=True,  # 열 너비 자동 조정
            update_mode=GridUpdateMode.NO_UPDATE  # ✅ 핵심! 클릭해도 아무 일 없음
        )
        
    with tabs[5]:
        
        st.header("Ranking")
        # CSV 파일 로드
        csv_file = "profits_history.csv"
        df = pd.read_csv(csv_file)
        df["date"] = pd.to_datetime(df["date"])

        # 봇 이름 목록 가져오기
        bot_names = df["bot_name"].unique().tolist()
        selected_bots = st.multiselect("🤖 봇 선택", bot_names, default=bot_names)

        # 수익률 종류 선택
        roi_option = st.radio(
            "📈 수익률 종류 선택",
            ("realized_roi", "unrealized_roi", "total_roi"),
            index=2,
            horizontal=True,
            format_func=lambda x: {
                "realized_roi": "실현 수익률",
                "unrealized_roi": "미실현 수익률",
                "total_roi": "총 수익률"
            }[x]
        )

        # 오늘 날짜 기준 데이터만 추출
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_df = df[df["date"] == today_str]
        today_df = today_df[today_df["bot_name"].isin(selected_bots)]

        # 등수 계산 (수익률 높은 순)
        if not today_df.empty:
            today_df = today_df.copy()
            today_df["rank"] = today_df[roi_option].rank(ascending=False, method='min').astype(int)
            today_df = today_df.sort_values("rank")

            st.subheader("🏆 오늘 수익률 순위")
            st.dataframe(today_df[["bot_name", roi_option, "rank"]].rename(columns={
                "bot_name": "Bot 이름",
                roi_option: "수익률 (%)",
                "rank": "등수"
            }), use_container_width=True)
        else:
            st.warning("오늘 날짜 기준 데이터가 없습니다.")

        # 선택된 봇 기준 전체 기간 시계열 그래프
        filtered_df = df[df["bot_name"].isin(selected_bots)]

        fig = px.line(
            filtered_df,
            x="date",
            y=roi_option,
            color="bot_name",
            markers=True,
            title=f"📊 날짜별 {roi_option.replace('_roi', '').capitalize()} 수익률 변화",
            labels={roi_option: "ROI (%)", "date": "날짜"}
        )

        st.plotly_chart(fig, use_container_width=True)
    

    with tabs[6]:
        
        st.header("Setting")

        # JSON 파일 읽기
        file_path = "./dashboard_web/trading_logic.json"
        with open(file_path, "r", encoding="utf-8") as file:
            trading_logic = json.load(file)

        available_buy_logic = trading_logic["available_buy_logic"]
        available_sell_logic = trading_logic["available_sell_logic"]
        available_take_profit_logic = trading_logic["available_take_profit_logic"]
        available_stop_loss_logic = trading_logic["available_stop_loss_logic"]
                
        # 선택할 옵션 리스트
        auto_trading_bots = list(UserInfo.scan())
        print(f"AutoTrading BOTS: {auto_trading_bots}")
        # 봇 이름 추출 및 중복 제거
        bot_names = sorted({item.trading_bot_name for item in auto_trading_bots if item.trading_bot_name is not None})
        # buy_trading_logics = {item.buy_trading_logic for item in auto_trading_bots if item.buy_trading_logic is not None}
        selected_bot_name = st.selectbox("봇을 선택하세요.", bot_names)

        # 선택된 봇에 해당하는 거래 내역 가져오기
        if selected_bot_name:
            selected_bot = [item for item in auto_trading_bots if item.trading_bot_name == selected_bot_name][0]
            print(f"Selected Bot: {selected_bot.id}")
            trading_bot = list(UserInfo.query(selected_bot.id))[0]
            
            print(f"Trading buy logic: {trading_bot.buy_trading_logic}")

            target_method = st.radio(
                "매수 금액을 어떻게 설정할까요?",
                ["직접 입력", "자본 비율 (%)"],
                index=1,
                horizontal=True,
                key=f'target_method_setting'
            )

            if target_method == "직접 입력":
                target_trade_value_krw = st.number_input("🎯 목표 매수 금액 (KRW)", min_value=10000, step=10000, value=trading_bot.target_trade_value_krw, key=f'target_trade_value_krw_setting')
                target_trade_value_ratio = None
                min_trade_value = 0
            else:
                target_trade_value_ratio = st.slider("💡 초기 자본 대비 매수 비율 (%)", 1, 100, trading_bot.target_trade_value_ratio, key=f'target_trade_value_ratio_setting') #마우스 커서로 왔다갔다 하는 기능
                min_trade_value = st.number_input("💰 최소 매수금액 (KRW)", min_value=0, value=trading_bot.min_trade_value, step=1000000, key=f"min_trade_value_setting")
                target_trade_value_krw = None  # 실제 시뮬 루프에서 매일 계산

            selected_buy_trading_logics = st.multiselect(
                "매수 로직 리스트",
                options=list(available_buy_logic.keys()),        # 전체 선택지
                default=[k for k, v in available_buy_logic.items() if v in trading_bot.buy_trading_logic] # 현재 봇에 설정된 매수 로직
            )

            selected_buy_trading_logics_values = [available_buy_logic[key] for key in selected_buy_trading_logics]

            selected_sell_trading_logics = st.multiselect(
                "매도 로직 리스트",
                options=list(available_sell_logic.keys()),
                default=[k for k, v in available_sell_logic.items() if v in trading_bot.sell_trading_logic] # 현재 봇에 설정된 매도 로직
            )

            selected_sell_trading_logics_values = [available_sell_logic[key] for key in selected_sell_trading_logics]

            take_profit_use_yn = st.checkbox("익절 조건 사용", value=trading_bot.take_profit_logic.use_yn, key="take_profit_use_yn")

            if trading_bot.take_profit_logic.name in list(available_take_profit_logic.values()):
                take_profit_index = list(available_take_profit_logic.values()).index(trading_bot.take_profit_logic.name)
            else:
                take_profit_index = 0  # 없을 경우 첫 번째 값으로

            selected_take_profit_logic = st.selectbox("익절 방식 선택", list(available_take_profit_logic.keys()), index=take_profit_index, key="take_profit_logic")
            take_profit_logic_name = available_take_profit_logic[selected_take_profit_logic]
            take_profit_ratio = st.number_input("익절 기준 (%)", value=float(trading_bot.take_profit_logic.params.ratio), min_value=0.0, key="take_profit_ratio_setting")

            stop_loss_use_yn = st.checkbox("손절 조건 사용", value=trading_bot.stop_loss_logic.use_yn, key="stop_loss_use_yn")

            if trading_bot.stop_loss_logic.name in list(available_stop_loss_logic.values()):
                stop_loss_index = list(available_stop_loss_logic.values()).index(trading_bot.stop_loss_logic.name)
            else:
                stop_loss_index = 0  # 없을 경우 첫 번째 값으로

            selected_stop_loss_logic = st.selectbox("손절 방식 선택", list(available_stop_loss_logic.keys()), index=stop_loss_index, key="stop_loss_logic")
            stop_loss_logic_name = available_stop_loss_logic[selected_stop_loss_logic]
            stop_loss_ratio = st.number_input("손절 기준 (%)", value=float(trading_bot.stop_loss_logic.params.ratio), min_value=0.0, key="stop_loss_ratio_setting")

            if st.button("저장", key="save_bot_settings", use_container_width=True, disabled=False if st.session_state["username"] == selected_bot.id else True):
                
                dynamodb_executor = DynamoDBExecutor()
                pk_name = 'id'
                
                kst = timezone("Asia/Seoul")
                # 현재 시간을 KST로 변환
                current_time = datetime.now(kst)
                updated_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성
                updated_at_dt = current_time.strftime("%Y-%m-%d %H:%M:%S")

                data_model = UserInfo(
                    id=selected_bot.id,
                    updated_at=updated_at,
                    updated_at_dt=updated_at_dt,
                    buy_trading_logic=selected_buy_trading_logics_values,
                    sell_trading_logic=selected_sell_trading_logics_values,
                    take_profit_logic={
                        "use_yn": take_profit_use_yn,
                        "name": take_profit_logic_name,
                        "params": {
                            "ratio": take_profit_ratio
                        }
                    },
                    stop_loss_logic={
                        "use_yn": stop_loss_use_yn,
                        "name": stop_loss_logic_name,
                        "params": {
                            "ratio": stop_loss_ratio
                        }
                    },
                    min_trade_value=min_trade_value,
                    target_trade_value_krw=target_trade_value_krw,
                    target_trade_value_ratio=target_trade_value_ratio,
                )

                result = dynamodb_executor.execute_update(data_model, pk_name)
                
                st.success(f"봇 설정이 저장되었습니다. {selected_bot}")
        
    with tabs[7]:
        
        st.title("📊 Today's UpDown!")

        user_id = 'id1' #임시 아이디 고정
        
        # ✅ 종목 불러오기
        kospi_kosdaq150 = list(StockSymbol.scan(
            filter_condition=((StockSymbol.type == 'kospi200') | (StockSymbol.type == 'kosdaq150'))
        ))
        kosdaq_all_result = list(StockSymbol2.scan(
            filter_condition=(StockSymbol2.type == 'kosdaq')
        ))
        sorted_items = sorted(
            kospi_kosdaq150,
            key=lambda x: ({'kospi200': 1, 'kosdaq150': 2}.get(getattr(x, 'type', ''), 99), getattr(x, 'symbol_name', ''))
        )

        # ✅ 종목 분류
        kospi200_items = [row for row in sorted_items if getattr(row, 'type', '') == 'kospi200']
        kosdaq150_items = [row for row in sorted_items if getattr(row, 'type', '') == 'kosdaq150']
        kosdaq_items = [row for row in kosdaq_all_result if getattr(row, 'type', '') == 'kosdaq']

        kospi200_names = [row.symbol_name for row in kospi200_items]
        kosdaq150_names = [row.symbol_name for row in kosdaq150_items]
        kosdaq_all_names = [row.symbol_name for row in kosdaq_items]
        all_symbol_names = list(set(row.symbol_name for row in (sorted_items + kosdaq_items)))

        # ✅ symbol mapping
        symbol_options_main = {row.symbol_name: row.symbol for row in sorted_items}
        symbol_options_kosdaq = {row.symbol_name: row.symbol for row in kosdaq_items}
        symbol_options = {**symbol_options_main, **symbol_options_kosdaq}

        # ✅ 세션 상태 초기화
        if "selected_stocks" not in st.session_state:
            st.session_state["selected_stocks2"] = []

        # ✅ 버튼 UI
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 4])
        

        with col1:
            if st.button("✅ 전체 선택", key="btn_all"):
                st.session_state["selected_stocks2"] = list(set(
                    st.session_state["selected_stocks2"] + all_symbol_names
                ))

        with col2:
            if st.button("🏦 코스피 200 추가", key="btn_kospi"):
                st.session_state["selected_stocks2"] = list(set(
                    st.session_state["selected_stocks2"] + kospi200_names
                ))

        with col3:
            if st.button("📈 코스닥 150 추가", key="btn_kosdaq150"):
                st.session_state["selected_stocks2"] = list(set(
                    st.session_state["selected_stocks2"] + kosdaq150_names
                ))

        with col4:
            if st.button("📊 코스닥 전체 추가", key="btn_kosdaq_all"):
                st.session_state["selected_stocks2"] = list(set(
                    st.session_state["selected_stocks2"] + kosdaq_all_names
                ))

        with col5:
            if st.button("❌ 선택 해제", key="btn_clear"):
                st.session_state["selected_stocks2"] = []

        # ✅ 유효 종목만 필터링
        valid_selected_stocks = [
            s for s in st.session_state.get("selected_stocks2", []) if s in symbol_options
        ]

        # ✅ 선택 수 표시
        st.markdown(f"🔎 **선택된 종목 수: {len(valid_selected_stocks)} 종목**")

        # ✅ 종목 선택 UI
        selected_stocks = st.multiselect(
            "📌 원하는 종목 선택",
            options=all_symbol_names,
            default=valid_selected_stocks,
            key = "selected_stocks2"
        )
        selected_symbols = [symbol_options[name] for name in selected_stocks]

        if st.button("📡 등락률 분석 요청"):

            if not selected_symbols:
                st.warning("📌 최소 1개 이상의 종목을 선택하세요.")
            else:
                with st.spinner("서버에 요청 중..."):
                    api_url = f"{backend_base_url}/stock/price-change/selected"
                    #조건 입력값
                    payload = {
                        "user_id": user_id,
                        "symbols": selected_symbols
                    }

                    response = requests.post(api_url, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        if data["status"] == "success":
                            presigned_url = data["result_presigned_url"]
                            df = pd.read_csv(presigned_url)
                            
                            st.session_state["analyzed_df"] = df  # ✅ 분석 결과 저장
                            st.success("✅ 분석 완료!")
                            
                            # ✅ 업종별 통계 계산
                            industry_summary = (
                                df.groupby("industry")
                                .agg(종목수=("symbol", "count"), 평균등락률=("change_pct", "mean"))
                                .reset_index()
                                .sort_values(by="평균등락률", ascending=False)
                            )

                            st.subheader("🏭 업종별 평균 등락률")
                            st.dataframe(industry_summary)
                                                        
                            import ast

                            # 문자열을 리스트로
                            df["theme"] = df["theme"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
                            # theme가 리스트인 상태라고 가정
                            df_exploded = df.explode("theme")

                            # theme가 None인 경우 제외
                            df_exploded = df_exploded[df_exploded["theme"].notna()]

                            # 평균 등락률 집계
                            theme_summary = (
                                df_exploded.groupby("theme")
                                .agg(종목수=("symbol", "count"), 평균등락률=("change_pct", "mean"))
                                .reset_index()
                                .sort_values(by="평균등락률", ascending=False)
                            )

                            st.subheader("🏭 테마별 평균 등락률")
                            st.dataframe(theme_summary)

                            st.subheader("📈 상승 종목")
                            st.metric("상승 종목 개수", f"{len(df[df['change_pct'] > 0])}")
                            st.dataframe(df[df['change_pct'] > 0].sort_values(by='change_pct', ascending=False))

                            st.subheader("📉 하락 종목")
                            st.metric("하락 종목 개수",  f"{len(df[df['change_pct'] < 0])}")
                            st.dataframe(df[df['change_pct'] < 0].sort_values(by='change_pct'))

                            st.subheader("📋 전체 종목")
                            st.metric("📊 분석된 종목 수", f"{len(df)}")
                            st.dataframe(df)
                        else:
                            st.warning("⚠️ 분석 결과가 없습니다.")
                    else:
                        st.error("❌ 서버 요청 실패")

        search_query = st.text_input("🔎 종목명 또는 테마 키워드를 입력하세요", "")
        do_search = st.button("🔍 검색")

        if do_search and search_query.strip():
            matched_items = []
            lower_query = search_query.lower()
            seen_symbols = set()

            for row in (sorted_items + kosdaq_items):
                symbol = row.symbol
                if symbol in seen_symbols:
                    continue

                name = getattr(row, "symbol_name", "").lower()
                themes = [t.lower() for t in (row.theme or [])]

                if lower_query in name or any(lower_query in t for t in themes):
                    matched_items.append(row)
                    seen_symbols.add(symbol)

            if matched_items:
                search_symbols = [row.symbol for row in matched_items]

                with st.spinner("📡 검색 중..."):
                    api_url = f"{backend_base_url}/stock/price-change/selected"
                    payload = {"user_id": user_id, "symbols": search_symbols}
                    response = requests.post(api_url, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        if data["status"] == "success":
                            df = pd.read_csv(data["result_presigned_url"])
                            df["symbol"] = df["symbol"].astype(str).str.zfill(6)

                            def format_change(val):
                                if pd.isna(val): return "N/A"
                                val = round(val, 2)
                                return int(val) if val == int(val) else val

                            result_df = pd.DataFrame([
                                {
                                    "종목명": row.symbol_name,
                                    "종목코드": row.symbol,
                                    "종류": getattr(row, "type", "unknown"),
                                    "테마": ", ".join(row.theme) if row.theme else "-",
                                    "등락률(%)": (
                                        format_change(df[df["symbol"] == row.symbol]["change_pct"].values[0])
                                        if row.symbol in df["symbol"].values else "N/A"
                                    )
                                }
                                for row in matched_items
                            ])

                            def color_change(val):
                                if isinstance(val, (float, int)):
                                    if val > 0: return "color: green"
                                    elif val < 0: return "color: red"
                                return "color: gray"
                            

                            st.success(f"🔍 총 {len(result_df)}개 종목이 검색되었습니다. 상승: {len(df[df['change_pct'] > 0])}, 하락: {len(df[df['change_pct'] < 0])}")
                            styled_df = result_df.style.applymap(color_change, subset=["등락률(%)"])
                            st.dataframe(styled_df)

                            # 디버깅용 누락 종목 표시
                            missing = [row.symbol for row in matched_items if row.symbol not in df["symbol"].values]
                            if missing:
                                st.warning(f"❗ 등락률 누락된 종목: {missing}")

                        else:
                            st.warning("⚠️ 등락률을 불러오지 못했습니다.")
                    else:
                        st.error("❌ 서버 요청 실패")
            else:
                st.warning("❌ 해당하는 종목명 또는 테마가 없습니다.")
        
        # st.markdown("---")
        # st.subheader("🔍 종목 이름 또는 테마 키워드 검색")

        # search_query = st.text_input("🔎 종목명 또는 테마 키워드를 입력하세요", "").strip()

        # df = st.session_state.get("analyzed_df", None)  # ✅ 이전 분석 결과 불러오기
        # print(f"df: {df}")
        
        #         # symbol 컬럼이 숫자형이면 str로 변환
        # if df is not None:
        #     df["symbol"] = df["symbol"].astype(str)
    
        # if search_query:
        #     matched_items = []
        #     lower_query = search_query.lower()

        #     for row in (sorted_items + kosdaq_items):
        #         name = getattr(row, "symbol_name", "").lower()
        #         themes = [t.lower() for t in (row.theme or [])]

        #         if lower_query in name or any(lower_query in t for t in themes):
        #             matched_items.append(row)

        #     if matched_items:
        #         result_df = pd.DataFrame([
        #             {
        #                 "종목명": row.symbol_name,
        #                 "종목코드": row.symbol,
        #                 "종류": getattr(row, "type", "unknown"),
        #                 "테마": ", ".join(row.theme) if row.theme else "-",
        #                 "등락률(%)": round(df[df["symbol"] == row.symbol]["change_pct"].values[0], 2) if df is not None and row.symbol in df["symbol"].values else "N/A"
        #             }
        #             for row in matched_items
        #         ])
        #         st.success(f"🔍 총 {len(result_df)}개 종목이 검색되었습니다.")
        #         st.dataframe(result_df)
        #     else:
        #         st.warning("❌ 해당하는 종목명 또는 테마가 없습니다.")



# Streamlit 앱 진입점
initial_router()