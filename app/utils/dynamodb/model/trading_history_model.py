from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute
import time
import uuid


class TradingHistory(Model):
    class Meta:
        table_name = "fsts-trading-history"
        region = "ap-northeast-2"

    trading_bot_name = UnicodeAttribute(hash_key=True)  # ✅ PK
    created_at = NumberAttribute(range_key=True)  # ✅ SK (밀리세컨드 단위)
    updated_at = NumberAttribute(null=True)
    trading_logic = UnicodeAttribute()
    trade_date = NumberAttribute()
    symbol = UnicodeAttribute()
    symbol_name = UnicodeAttribute()
    position = UnicodeAttribute()
    price = NumberAttribute()
    quantity = NumberAttribute()
    data_type = UnicodeAttribute()