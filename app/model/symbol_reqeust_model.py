from pydantic import BaseModel
from typing import Dict, Optional, List

class SymbolRequestModel(BaseModel):
    user_id: str
    symbols: List[str]