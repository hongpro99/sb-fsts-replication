from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute


class AutoTrading(Model):
    class Meta:
        table_name = "fsts-auto-trading"
        region = "ap-northeast-2"

    # PK / SK
    trading_bot_name = UnicodeAttribute(hash_key=True)      # Primary Key
    created_at = NumberAttribute(range_key=True)            # Sort Key (epoch millis)

    # 필수 정보
    updated_at = NumberAttribute(null=True)                 # Optional 업데이트 시간
    trading_logic = UnicodeAttribute()                      # 사용한 전략
    trade_date = NumberAttribute()                          # 거래 일자 (yyyymmdd)
    symbol = UnicodeAttribute()                             # 종목 코드
    symbol_name = UnicodeAttribute()                        # 종목명
    position = UnicodeAttribute()                           # BUY / SELL
    price = NumberAttribute()                               # 매수 또는 매도 가격
    quantity = NumberAttribute()                            # 거래 수량
