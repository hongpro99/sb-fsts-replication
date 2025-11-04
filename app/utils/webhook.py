import numpy as np
import requests
from dotenv import load_dotenv
import os

# 환경 변수 파일 로드
load_dotenv()

class Webhook:
    
    def send_discord_webhook(self, message, bot_type):
        if bot_type == 'trading':
            webhook_url = os.getenv("DISCORD_TRADING_ALARM_WEBHOOK_URL")
            username = "Stock Trading Bot"
        if bot_type == 'alarm':
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            username = 'Stock Alarm Bot'
        data = {
            "content": message,
            "username": username,  # 원하는 이름으로 설정 가능
        }
        
        # 요청 보내기
        response = requests.post(webhook_url, json=data)
        
        # 응답 확인
        if response.status_code == 204:
            print("메시지가 성공적으로 전송되었습니다.")
        else:
            print(f"메시지 전송 실패: {response.status_code}, {response.text}")