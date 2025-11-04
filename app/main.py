import uuid
from fastapi import FastAPI, HTTPException
from typing import Optional
from datetime import date, datetime, timedelta
import pytz
import asyncio
import requests
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
import numpy as np
import os
from io import StringIO, BytesIO
import boto3
import json
from botocore.client import Config
import pandas as pd

from app.model.simulation_trading_bulk_model import SimulationTradingBulkModel
from app.model.simulation_trading_model import SimulationTradingModel
from app.model.symbol_reqeust_model import SymbolRequestModel
from app.utils.dynamodb.model.stock_symbol_model import StockSymbol, StockSymbol2
from app.scheduler import auto_trading_scheduler
from app.utils.auto_trading_bot import AutoTradingBot
from app.utils.database import get_db, get_db_session
from app.utils.crud_sql import SQLExecutor
from app.utils.dynamodb.model.simulation_history_model import SimulationHistory
from ecs.run_ecs_task import run_ecs_task
from app.utils.utils import setup_env
from ecs.run_ecs_task_local import run_ecs_task_local


app = FastAPI() 

# env 파일 로드
setup_env()

# 스케줄러 설정(병렬로 실행)
scheduler = BackgroundScheduler(timezone=timezone('Asia/Seoul'))

#3분 간격으로 실행
#scheduler.add_job(auto_trading_scheduler.scheduled_trading_bnuazz15bot_real_task, 'cron', day_of_week='mon-fri', hour='15', minute='15')# 월~금 3시 10분에 실행
scheduler.add_job(auto_trading_scheduler.scheduled_trading_schedulerbot_task, 'cron', day_of_week='mon-fri', hour='15', minute='10')  # 월~금 3시 10분에 실행
scheduler.add_job(auto_trading_scheduler.scheduled_trading_dreaminmindbot_task, 'cron', day_of_week='mon-fri', hour='15', minute='10')  # 월~금 3시 10분에 실행
#scheduler.add_job(auto_trading_scheduler.scheduled_trading_bnuazz15bot_task, 'cron', day_of_week='mon-fri', hour='15', minute='00') # 월~금 3시 10분에 실행
scheduler.add_job(auto_trading_scheduler.scheduled_trading_weeklybot_task, 'cron', day_of_week='mon-fri', hour='14', minute='30')# 금 3시 10분에 실행(주봉)


schedule_times = [
    # (9, 35),
    # (10, 5),
    # (11, 25),
    # (13, 25),
    (14, 35)
]

schedule_times2 = {
    (10, 00),
    (12, 00),
    (14, 00),
    (16, 00)

}

# for h, m in schedule_times:
#     scheduler.add_job(
#         auto_trading_scheduler.get_netbuy_summary_by_investor,
#         'cron',
#         day_of_week='mon-fri',
#         hour=h,
#         minute=m
#     )
    
# for h, m in schedule_times2:
#     scheduler.add_job(
#         auto_trading_scheduler.run_market_netbuy_summary,
#         'cron',
#         day_of_week='mon-fri',
#         hour=h,
#         minute=m
#     )    

scheduler.start()

@app.get("/trade")
async def trade():
    auto_trading_scheduler.scheduled_trading()
    return {"status": "trade 완료!!!"}

@app.post("/stock/simulate/single")
async def simulate_single_trade(data: SimulationTradingModel):
    
    simulation_data = data.model_dump(exclude_none=True)

    auto_trading_stock = AutoTradingBot(id=simulation_data["user_id"], virtual=False)
    start_date = datetime.fromisoformat(simulation_data["start_date"])
    end_date = datetime.fromisoformat(simulation_data["end_date"])

    data_df, assets, simulation_histories, = auto_trading_stock.simulate_trading(
        symbol=simulation_data["symbol"],
        stock_name=simulation_data["stock_name"],
        stock_type = simulation_data['stock_type'],
        start_date=start_date,
        end_date=end_date,
        target_trade_value_krw=simulation_data.get("target_trade_value_krw"),
        target_trade_value_ratio=simulation_data.get("target_trade_value_ratio"),
        min_trade_value=simulation_data.get("min_trade_value"),
        buy_trading_logic=simulation_data["buy_trading_logic"],
        sell_trading_logic=simulation_data["sell_trading_logic"],
        interval=simulation_data["interval"],
        buy_percentage=simulation_data.get("buy_percentage"),
        ohlc_mode = simulation_data["ohlc_mode"],
        rsi_period= simulation_data['rsi_period'],
        initial_capital = simulation_data.get('initial_capital'),
        take_profit_logic=simulation_data.get("take_profit_logic"),
        stop_loss_logic=simulation_data.get("stop_loss_logic"),
        indicators=simulation_data.get("indicators")
    )

    csv_url = save_df_to_s3(data_df, bucket_name="sb-fsts")

    # data_df_cleaned = data_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    # data_df_cleaned = data_df.replace([np.inf, -np.inf], np.nan)

    json_dict = {
        "data_url": csv_url,
        # "data_df": data_df_cleaned.to_dict(orient="records") if hasattr(data_df_cleaned, "to_dict") else data_df_cleaned,
        "assets": assets,
        "simulation_histories": simulation_histories
    }

    json_url = save_json_to_s3(json_dict, bucket_name="sb-fsts")

    response_dict = {
        "json_url": json_url
    }

    return response_dict


@app.post("/stock/simulate/bulk")
async def simulate_bulk_trade(data: SimulationTradingBulkModel):
    
    simulation_data = data.model_dump(exclude_none=True)

    auto_trading_stock = AutoTradingBot(id=simulation_data["user_id"], virtual=False)
    simulation_data["start_date"] = datetime.fromisoformat(simulation_data["start_date"])
    simulation_data["end_date"] = datetime.fromisoformat(simulation_data["end_date"])

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    # 마이크로초를 문자열로 만들어서 앞에서 4자리만 사용
    ms4 = f"{now.microsecond:06d}"[:4]
    
    timestamp_key = now.strftime("%Y%m%d_%H%M%S_") + ms4

    key = f'{timestamp_key}_{str(uuid.uuid4()).replace("-", "")[:16]}'  # 16자리 예시
    # key = str(uuid.uuid4())

    json_url = save_json_to_s3(simulation_data, bucket_name="sb-fsts", save_path=f"simulation-results/{key}/simulation_data.json")
    result_save_path = f"simulation-results/{key}/simulation_result.json"

    env = os.getenv("ENV", "dev")
    if env == "local":
        # 로컬 환경에서는 ECS 태스크를 실행하지 않고 바로 시뮬레이션 실행
        print(f"Running simulation locally for simulation_id: {key}")
        result = run_ecs_task_local(simulation_data, json_url, key, result_save_path)
        
        response_dict = {
            "simulation_id": key
        }

    else:
        # ECS 태스크 실행
        print(f"Running ECS task for simulation_id: {key}")
        # ECS 태스크 실행
        result = run_ecs_task(simulation_data, json_url, key, result_save_path)
        
        response_dict = {
            "simulation_id": key
        }

    return response_dict


@app.get('/stock/simulate/bulk/result')
async def get_simulation_bulk(simulation_id: str):

    item = SimulationHistory.get(simulation_id)

    result_presigned_url = ""
    status = item.status
    total_task_cnt = item.total_task_cnt
    completed_task_cnt = item.completed_task_cnt

    params_presigned_url = ""
    result_presigned_url = ""

    if status == "completed":
        
        s3_client = boto3.client('s3', region_name='ap-northeast-2', endpoint_url='https://s3.ap-northeast-2.amazonaws.com', config=boto3.session.Config(signature_version='s3v4'))
        bucket_name="sb-fsts"

        params_save_path = f"simulation-results/{simulation_id}/simulation_data.json"
        result_save_path = f"simulation-results/{simulation_id}/simulation_result.json"

        params_presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': params_save_path},
            ExpiresIn=3600
        )

        result_presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': result_save_path},
            ExpiresIn=3600
        )

    response_dict = {
        "status": status,
        "total_task_cnt": total_task_cnt,
        "completed_task_cnt": completed_task_cnt,
        "params_presigned_url": params_presigned_url,
        "result_presigned_url": result_presigned_url
    }

    return response_dict

@app.post("/stock/price-change/selected")
async def post_price_change_selected(data: SymbolRequestModel):
    
    simulation_data = data.model_dump(exclude_none=True)
    
    auto_trading_stock = AutoTradingBot(id=simulation_data["user_id"], virtual=False)
    
    import datetime
    today = datetime.date.today()
    print(today)
    start_date = (today - datetime.timedelta(days=5))
    end_date = today
    print(start_date, end_date)

    # ✅ symbol → name, type 매핑 준비
    symbol_info_map = {}

    # ✅ 먼저 StockSymbol (우선순위 높음)
    for item in list(StockSymbol.scan()):
        symbol_info_map[item.symbol] = {
            "name": item.symbol_name,
            "type": getattr(item, "type", "unknown"),
            "industry": getattr(item, "industry", "unknown"),
            "theme": getattr(item, "theme", "unknown")
        }

    # ✅ 그 다음 StockSymbol2 → 기존에 없는 symbol만 추가
    for item in list(StockSymbol2.scan()):
        if item.symbol not in symbol_info_map:
            symbol_info_map[item.symbol] = {
                "name": item.symbol_name,
                "type": getattr(item, "type", "unknown"),
                "industry": getattr(item, "industry", "unknown"),
                "theme": getattr(item, "theme", "unknown")
            }
        
    results = []

    for symbol in data.symbols:
        info = symbol_info_map.get(symbol, {"name": "Unknown", "type": "unknown","industry": "unknown", "theme": "unknown"})
        name = info["name"]
        stock_type = info["type"]
        industry= info["industry"]
        theme = info["theme"]
        try:
            klines = auto_trading_stock._get_ohlc(symbol, start_date, end_date)
            if len(klines) >= 2:
                prev_close = klines[-2].close
                curr_close = klines[-1].close
                pct = round((curr_close - prev_close) / prev_close * 100, 2)
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "stock_type": stock_type,
                    "industry": industry,
                    "theme": theme,
                    "change_pct": pct,
                    "current_close": curr_close,
                    
                })
        except Exception as e:
            print(f"❌ {symbol} 오류: {e}")

    df = pd.DataFrame(results)
    if df.empty:
        return {"status": "no_data", "result_presigned_url": ""}

    presigned_url = save_df_to_s3(df, bucket_name="sb-fsts", folder_prefix="price-change/")
    return {"status": "success", "result_presigned_url": presigned_url}
    
@app.get("/health")
async def health_check():
    print('health!!')
    return {"status": "healthy!!"}


def save_json_to_s3(response_dict, bucket_name, save_path="simulation-results/"):

    s3_client = boto3.client('s3', region_name='ap-northeast-2', endpoint_url='https://s3.ap-northeast-2.amazonaws.com', config=boto3.session.Config(signature_version='s3v4'))

    # JSON 데이터를 메모리 스트림으로 변환
    json_bytes = BytesIO(json.dumps(response_dict, ensure_ascii=False, indent=4, default=str).encode('utf-8'))

    s3_key = save_path

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json_bytes,
        ContentType='application/json'
    )

    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': s3_key},
        ExpiresIn=3600
    )
    return presigned_url


def save_df_to_s3(data_df, bucket_name, folder_prefix="simulation-results/"):
    # CSV로 변환 (메모리 상에서)
    csv_buffer = StringIO()
    data_df.to_csv(csv_buffer, index=False)

    # key = "20250507"
    key = uuid.uuid4()
    # S3 경로 생성
    s3_key = f"{folder_prefix}{key}.csv"
    
    s3_client = boto3.client('s3', region_name='ap-northeast-2', endpoint_url='https://s3.ap-northeast-2.amazonaws.com', config=boto3.session.Config(signature_version='s3v4'))
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=csv_buffer.getvalue()
    )

    # Presigned URL 생성 (유효시간 1시간)
    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': s3_key},
        ExpiresIn=3600
    )
    return presigned_url