from app.legacy.auto_trading_stock import AutoTradingStock
from dotenv import load_dotenv
import os


#환경 파일 로드
load_dotenv()

def create_auto_trading_stock(user_choice: str):
    """사용자로부터 모의투자 여부를 입력받아 객체 생성"""
    
    if user_choice == "mock":
        return AutoTradingStock(
        # HTS 로그인 ID  예) soju06
        id=os.getenv('MOCK_YOUR_ID'),
        account=os.getenv('MOCK_ACCOUNT_NO'),
        real_appkey = os.getenv('REAL_API_KEY'),
        real_secretkey= os.getenv('REAL_API_SECRET'),
        # 앱 키  예) Pa0knAM6JLAjIa93Miajz7ykJIXXXXXXXXXX
        virtual_id = os.getenv('MOCK_YOUR_ID'),
        virtual_appkey=os.getenv('MOCK_API_KEY'),
        # 앱 시크릿 키  예) V9J3YGPE5q2ZRG5EgqnLHn7XqbJjzwXcNpvY . . .
        virtual_secretkey=os.getenv('MOCK_API_SECRET'),
        # 앱 키와 연결된 계좌번호  예) 00000000-01
        virtual=True
        )
    elif user_choice == "real":
        return AutoTradingStock(
        id=os.getenv('REAL_YOUR_ID'),
        # 앱 키  예) Pa0knAM6JLAjIa93Miajz7ykJIXXXXXXXXXX
        real_appkey=os.getenv('REAL_API_KEY'),
        # 앱 시크릿 키  예) V9J3YGPE5q2ZRG5EgqnLHn7XqbJjzwXcNpvY . . .
        real_secretkey=os.getenv('REAL_API_SECRET'), # 발급받은 App Secret
        # 앱 키와 연결된 계좌번호  예) 00000000-01
        account=os.getenv('REAL_ACCOUNT_NO'),
        virtual=False
        )
    else:
        raise ValueError("잘못된 입력입니다. 'y' 또는 'n'을 입력하세요.")
