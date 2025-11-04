from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute


class AutoTradingBalance(Model):
    class Meta:
        table_name = "fsts-auto-trading-balance"
        region = "ap-northeast-2"

    trading_bot_name = UnicodeAttribute(hash_key=True)
    symbol = UnicodeAttribute(range_key=True)
    updated_at = NumberAttribute()          # 마지막 업데이트 시각
    symbol_name = UnicodeAttribute()
    market = UnicodeAttribute()
    quantity = NumberAttribute()
    avg_price = NumberAttribute()               # 평균단가
    amount = NumberAttribute()              # 평가금액
    profit = NumberAttribute()
    profit_rate = NumberAttribute()
