# app/__init__.py
import os
from dotenv import load_dotenv

# 📍 루트 디렉토리 기준으로 .env 경로 생성
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# ✅ .env 로드 (한 번만 실행됨)
load_dotenv(ENV_PATH)

# 디버그용 확인
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️  [WARNING] .env 파일 로드 실패 또는 키 누락")
else:
    print("✅  .env 파일 로드 성공:", ENV_PATH)
