from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, UnicodeSetAttribute
import time
import uuid

class StockSymbol(Model):
    class Meta:
        table_name = "fsts-stock-symbol"
        region = "ap-northeast-2"

    symbol = UnicodeAttribute(hash_key=True)  # ✅ PK
    created_at = NumberAttribute()
    updated_at = NumberAttribute(null=True)
    symbol_name = UnicodeAttribute()
    type = UnicodeAttribute() #kospi, kosdaq
    market_cap = NumberAttribute(null=True)
    industry = UnicodeAttribute(null=True)
    theme = UnicodeSetAttribute(null=True)
class StockSymbol2(Model):
    class Meta:
        table_name = "fsts-stock-symbol2"
        region = "ap-northeast-2"

    symbol = UnicodeAttribute(hash_key=True)  # ✅ PK
    created_at = NumberAttribute(range_key=True) #SK
    updated_at = NumberAttribute(null=True)
    symbol_name = UnicodeAttribute()
    type = UnicodeAttribute() #kospi, kosdaq
    market_cap = NumberAttribute(null=True)
    industry = UnicodeAttribute(null=True)
    theme = UnicodeSetAttribute(null=True)
        
#         # ✅ 테이블 생성
# if not StockSymbol2.exists():
#     StockSymbol2.create_table(read_capacity_units=5, write_capacity_units=5, wait=True)
#     print("✅ 테이블 생성 완료")
# else:
#     print("ℹ️ 테이블이 이미 존재합니다.")