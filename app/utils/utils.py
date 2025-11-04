import os
from dotenv import load_dotenv


def setup_env():

    # 1️⃣ 환경 변수를 통해 어떤 env 파일을 쓸지 결정
    env_mode = os.getenv("ENV", "dev")

    # 2️⃣ env 파일 매핑
    env_files = {
        "local": ".env.local",
        "dev": ".env.dev",
        "prd": ".env.prd",
        "stage": ".env.stage"
    }

    # 3️⃣ 해당 env 파일 불러오기
    load_dotenv(dotenv_path=env_files.get(env_mode, ".env.dev"))

    # ✅ 테스트용 출력
    print("ENV:", env_mode)