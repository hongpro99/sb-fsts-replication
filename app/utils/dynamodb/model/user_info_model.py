from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, ListAttribute, BooleanAttribute, MapAttribute
import time
import uuid


class StopLossLogicParams(MapAttribute):
    ratio = NumberAttribute()


class StopLossLogic(MapAttribute):
    name = UnicodeAttribute()
    params = StopLossLogicParams()
    use_yn = BooleanAttribute()


class UserInfo(Model):
    class Meta:
        table_name = "fsts-user-info"
        region = "ap-northeast-2"

    id = UnicodeAttribute(hash_key=True)  # ✅ PK
    created_at = NumberAttribute()
    created_at_dt = UnicodeAttribute(null=True)
    updated_at = NumberAttribute(null=True)
    updated_at_dt = UnicodeAttribute(null=True)
    password = UnicodeAttribute()
    name = UnicodeAttribute()
    app_key = UnicodeAttribute()
    secret_key = UnicodeAttribute()
    kis_id = UnicodeAttribute()
    account = UnicodeAttribute()
    virtual_kis_id =  UnicodeAttribute(null=True)
    virtual_app_key =  UnicodeAttribute(null=True)
    virtual_secret_key =  UnicodeAttribute(null=True)
    virtual_account =  UnicodeAttribute(null=True)
    buy_trading_logic = ListAttribute(of=UnicodeAttribute)
    sell_trading_logic = ListAttribute(of=UnicodeAttribute)
    max_allocation = NumberAttribute()
    interval = UnicodeAttribute()
    take_profit_logic = StopLossLogic()
    stop_loss_logic = StopLossLogic()
    trading_bot_name = UnicodeAttribute(null=True)
    target_trade_value_ratio = NumberAttribute(null=True)
    target_trade_value_krw = NumberAttribute(null=True)
    min_trade_value = NumberAttribute(null=True)