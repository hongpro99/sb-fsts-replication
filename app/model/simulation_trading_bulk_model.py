from pydantic import BaseModel
from typing import Dict, Optional, List


class SimulationTradingBulkModel(BaseModel):
    user_id: str
    start_date: str
    end_date: str
    target_trade_value_krw: Optional[int]
    target_trade_value_ratio: Optional[float]
    min_trade_value: Optional[int]
    selected_stocks: List[str]
    selected_symbols: Dict[str, str]
    stock_type : Dict[str, str]
    interval: str
    buy_trading_logic: Optional[List[str]]
    sell_trading_logic: Optional[List[str]]
    buy_condition_yn: Optional[bool]
    buy_percentage: Optional[float]
    initial_capital: Optional[float]
    rsi_buy_threshold: Optional[int]
    rsi_sell_threshold: Optional[int]
    rsi_period: Optional[int]
    take_profit_logic: Optional[dict]
    stop_loss_logic: Optional[dict]