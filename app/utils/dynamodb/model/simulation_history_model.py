from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, MapAttribute
import time
import uuid


class SimulationHistory(Model):
    class Meta:
        table_name = "fsts-simulation-history"
        region = "ap-northeast-2"

    simulation_id = UnicodeAttribute(hash_key=True)  # ✅ PK
    created_at = NumberAttribute()
    created_at_dt = UnicodeAttribute(null=True)
    updated_at = NumberAttribute(null=True)
    updated_at_dt = UnicodeAttribute(null=True)
    type = UnicodeAttribute()
    status = UnicodeAttribute()
    trigger_user = UnicodeAttribute()
    trigger_type = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    total_task_cnt = NumberAttribute(null=True)
    completed_task_cnt = NumberAttribute(null=True)
    initial_capital = NumberAttribute(null=True)
    simulation_params = UnicodeAttribute(null=True)