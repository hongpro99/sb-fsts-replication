from pydantic import BaseModel
from typing import Dict, Optional, List


class SimulationTradingModel(BaseModel):
    user_id: str
    symbol: str
    stock_name: str
    stock_type : str
    start_date: str
    end_date: str
    target_trade_value_krw: Optional[int]
    target_trade_value_ratio: Optional[float]
    min_trade_value: Optional[int]
    buy_trading_logic: Optional[List[str]]
    sell_trading_logic: Optional[List[str]]
    interval: str
    buy_percentage: Optional[float]
    ohlc_mode: Optional[str]
    rsi_buy_threshold: int
    rsi_sell_threshold: int
    rsi_period: int
    initial_capital: Optional[float]
    take_profit_logic: Optional[dict]
    stop_loss_logic: Optional[dict]
    indicators: Optional[List[dict]]
