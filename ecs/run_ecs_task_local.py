import boto3
from pytz import timezone
from datetime import datetime
import os

from app.utils.dynamodb.crud import DynamoDBExecutor
from app.utils.dynamodb.model.simulation_history_model import SimulationHistory
from ecs.task_job import run_job


def run_ecs_task_local(simulation_data: dict, SIMULATION_DATA_S3_PATH: str, simulation_id: str, result_save_path:str):

    os.environ["SIMULATION_DATA_S3_PATH"] = SIMULATION_DATA_S3_PATH
    os.environ["simulation_id"] = simulation_id
    os.environ["result_save_path"] = result_save_path

    user_id = simulation_data['user_id']

    _save_trading_history(user_id, simulation_id, simulation_data)

    response = run_job()    

    print(response)


def _save_trading_history(user_id: str, simulation_id: str, simulation_data: dict):
    """
    시뮬레이션 히스토리 저장
    """

    initial_capital = simulation_data['initial_capital']

    dynamodb_executor = DynamoDBExecutor()
    # 한국 시간대
    kst = timezone("Asia/Seoul")
    # 현재 시간을 KST로 변환
    current_time = datetime.now(kst)
    created_at = int(current_time.timestamp() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성
    created_at_dt = current_time.strftime("%Y-%m-%d %H:%M:%S")
    updated_at = None
    updated_at_dt = None
    type = 'bulk' # single, bulk
    status = 'starting' # starting, running, completed
    trigger_type = 'manual' # manual, auto
    description = None
    total_task_cnt = 0
    completed_task_cnt = 0

    data_model = SimulationHistory(
        simulation_id=simulation_id,
        created_at=created_at,
        created_at_dt=created_at_dt,
        updated_at=updated_at,
        updated_at_dt=updated_at_dt,
        type=type,
        status=status,
        trigger_user=user_id,
        trigger_type=trigger_type,
        description=description,
        total_task_cnt=total_task_cnt,
        completed_task_cnt=completed_task_cnt,
        initial_capital=initial_capital,
        # simulation_params=simulation_data
    )

    result = dynamodb_executor.execute_save(data_model)
    print(f"Trading history for {simulation_id} saved successfully: {result}")
    return result