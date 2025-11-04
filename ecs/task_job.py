import os
import sys
import requests
from io import StringIO, BytesIO
import boto3
import json
from datetime import datetime
from pytz import timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.dynamodb.model.simulation_history_model import SimulationHistory
from app.utils.dynamodb.crud import DynamoDBExecutor
from app.utils.auto_trading_bot import AutoTradingBot


def read_json_from_presigned_url(presigned_url):
    print(f"presigned_url = {presigned_url}")
    
    response = requests.get(presigned_url)
    response.raise_for_status()  # 오류 발생 시 예외 발생
    
    # response.text 또는 response.json() 선택 가능
    # 만약 JSON 파일 구조가 DataFrame으로 바로 변환 가능한 형식이면:
    data = response.json()
    
    return data

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


def run_job():
    simulation_data_url = os.environ.get("SIMULATION_DATA_S3_PATH")
    simulation_id = os.environ.get("simulation_id")
    result_save_path = os.environ.get("result_save_path")

    simulation_data = read_json_from_presigned_url(simulation_data_url)

    auto_trading_stock = AutoTradingBot(id=simulation_data["user_id"], virtual=False)
    simulation_data["start_date"] = datetime.fromisoformat(simulation_data["start_date"])
    simulation_data["end_date"] = datetime.fromisoformat(simulation_data["end_date"])
    simulation_data["simulation_id"] = simulation_id

    dynamodb_executor = DynamoDBExecutor()

    pk_name = 'simulation_id'

    # 한국 시간대
    kst = timezone("Asia/Seoul")
    # 현재 시간을 KST로 변환
    current_time = datetime.now(kst)
    updated_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성
    updated_at_dt = current_time.strftime("%Y-%m-%d %H:%M:%S")
    status = "running"

    data_model = SimulationHistory(
        simulation_id=simulation_id,
        updated_at=updated_at,
        updated_at_dt=updated_at_dt,
        status=status
    )

    result = dynamodb_executor.execute_update(data_model, pk_name)

    assets, simulation_histories, failed_stocks = auto_trading_stock.simulate_trading_bulk(simulation_data)

    json_dict = {
        "assets": assets,
        "simulation_histories": simulation_histories,
        # "data_df": data_df_cleaned.to_dict(orient="records") if hasattr(data_df_cleaned, "to_dict") else data_df_cleaned,
        "failed_stocks": failed_stocks
    }

    simulation_result_json_url = save_json_to_s3(json_dict, bucket_name="sb-fsts", save_path=result_save_path)

    print(f'simulation_result_json_url = {simulation_result_json_url}')

    # 한국 시간대
    kst = timezone("Asia/Seoul")
    # 현재 시간을 KST로 변환
    current_time = datetime.now(kst)
    updated_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성
    updated_at_dt = current_time.strftime("%Y-%m-%d %H:%M:%S")
    status = "completed"

    data_model = SimulationHistory(
        simulation_id=simulation_id,
        updated_at=updated_at,
        updated_at_dt=updated_at_dt,
        status=status
    )

    result = dynamodb_executor.execute_update(data_model, pk_name)

if __name__ == "__main__":
    run_job()
    print("ECS task completed successfully.")