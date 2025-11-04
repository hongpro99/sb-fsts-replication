from pynamodb.transactions import TransactWrite
from pynamodb.connection import Connection
from botocore.exceptions import ClientError
import time

from app.utils.dynamodb.model.trading_history_model import TradingHistory


class DynamoDBExecutor:
    def __init__(self):
        pass

    def add_trade(self, trading_bot_name, symbol, position, price, quantity, data_type):
        max_retries = 3  # 최대 재시도 횟수
        retry_count = 0

        while retry_count < max_retries:
            try:
                created_at = int(time.time() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성

                new_trade = TradingHistory(
                    trading_bot_name=trading_bot_name,
                    created_at=created_at,
                    updated_at=None,
                    symbol=symbol,
                    position=position,
                    price=price,
                    quantity=quantity,
                    data_type=data_type
                )

                connection = Connection(region="ap-northeast-2")

                with TransactWrite(connection=connection) as transaction:
                    transaction.save(new_trade, condition=(TradingHistory.created_at.does_not_exist()))
                    print(f"✅ 트랜잭션 성공: {created_at}")
                    return True  # 성공적으로 저장되면 종료

            except ClientError as e:
                if e.response["Error"]["Code"] == "TransactionCanceledException":
                    print("❌ 중복된 created_at 감지! 새로운 값으로 재시도...")
                    retry_count += 1
                else:
                    raise  # 다른 에러 발생 시 예외 던지기

        print("🚨 최대 재시도 횟수 초과! 거래 저장 실패")
        return False


    def execute_save(self, data_model):
        max_retries = 3  # 최대 재시도 횟수
        retry_count = 0

        while retry_count < max_retries:
            try:
                connection = Connection(region="ap-northeast-2")

                created_at = int(time.time() * 1000)  # ✅ 밀리세컨드 단위로 SK 생성

                with TransactWrite(connection=connection) as transaction:
                    model_class = type(data_model)

                    if hasattr(model_class, 'created_at'):
                        transaction.save(data_model, condition=(model_class.created_at.does_not_exist()))
                    else:
                        transaction.save(data_model)  # 조건 없이 저장
                    print(f"✅ 트랜잭션 성공: {created_at}")
                    return True  # 성공적으로 저장되면 종료

            except ClientError as e:
                if e.response["Error"]["Code"] == "TransactionCanceledException":
                    print("❌ 중복된 created_at 감지! 새로운 값으로 재시도...")
                    retry_count += 1
                else:
                    raise  # 다른 에러 발생 시 예외 던지기

        print("🚨 최대 재시도 횟수 초과! 거래 저장 실패")
        return False
    

    def execute_update(self, data_model, pk_name, sk_name=None):
        max_retries = 3
        retry_count = 0

        excluded_fields = [pk_name]
        if sk_name is not None:
            excluded_fields.append(sk_name)

        data_model_dict = data_model.attribute_values
        
        while retry_count < max_retries:
            try:
                connection = Connection(region="ap-northeast-2")

                with TransactWrite(connection=connection) as transaction:
                    model_class = type(data_model)

                    print(f'data_model_dict = {data_model_dict}')

                    # ✅ 동적 업데이트 필드 구성
                    update_actions = [
                        getattr(model_class, field_name).set(value)
                        for field_name, value in data_model_dict.items()
                        if field_name not in excluded_fields
                    ]

                    transaction.update(
                        data_model,
                        actions=update_actions
                    )

                    print("✅ 동적 필드 업데이트 성공")
                    return True

            except ClientError as e:
                if e.response["Error"]["Code"] == "TransactionCanceledException":
                    print("❌ 업데이트 실패, 재시도...")
                    reasons = e.response.get("CancellationReasons")
                    print("❌ 트랜잭션 취소 이유:", reasons)
                    retry_count += 1
                else:
                    reasons = e.response.get("CancellationReasons")
                    print("❌ 트랜잭션 취소 이유:", reasons)
                    raise

        print("🚨 최대 재시도 횟수 초과! 업데이트 실패")
        return False