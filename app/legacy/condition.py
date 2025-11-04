def get_ohlc_by_date(ohlc_data, current_date, d_date=0):
    """
    현재 날짜와 d_date 오프셋을 기준으로 OHLC 데이터를 반환.
    
    :param ohlc_data: OHLC 데이터 리스트 (시간순 정렬된 데이터)
    :param current_date: 기준 날짜 (datetime 또는 str 형식)
    :param d_date: 음수는 과거, 0은 현재, 양수는 미래 데이터를 가져옴
    :return: OHLC 데이터 (시가, 고가, 저가, 종가)
    """
    # 현재 날짜 기준으로 데이터 인덱스 찾기
    for i, candle in enumerate(ohlc_data):
        candle_date = candle.time  # datetime 형식 가정
        if candle_date == current_date:
            target_index = i + d_date
            if 0 <= target_index < len(ohlc_data):
                target_candle = ohlc_data[target_index]
                return {
                    "open": float(target_candle.open),
                    "high": float(target_candle.high),
                    "low": float(target_candle.low),
                    "close": float(target_candle.close),
                    "time": target_candle.time,
                }
            else:
                return None  # 범위를 벗어난 경우 None 반환

    raise ValueError(f"현재 날짜 {current_date}에 해당하는 데이터를 찾을 수 없습니다.")
