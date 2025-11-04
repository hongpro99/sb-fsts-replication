from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

DB_ID = 'sbmaster'
DB_PASSWORD = 'sbmaster123'
DATABASE_URL = f"postgresql://{DB_ID}:{DB_PASSWORD}@sb-rds.cp9lsfxv5if3.ap-northeast-2.rds.amazonaws.com/fsts"

# 엔진 설정
engine = create_engine(DATABASE_URL)

# 세션 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    
    db = SessionLocal()
    
    return db

# 세션 생성 함수
@contextmanager
def get_db_session():
    db = SessionLocal()  # 세션 생성
    try:
        yield db  # 세션을 호출자에게 반환
    finally:
        db.close()  # 작업 완료 후 세션 종료