from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
from fastapi import HTTPException


class SQLExecutor:
    def __init__(self):
        pass

    # SELECT 쿼리 실행
    def execute_select(self, db: Session, query: str, params: dict = None):
        try:
            result = db.execute(text(query), params).mappings()
            return result.all()
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    # INSERT 쿼리 실행
    def execute_insert(self, db: Session, query: str, params: dict = None):
        try:
            result = db.execute(text(query), params).mappings()
            inserted_record = None
            inserted_record = result.all()
            db.commit()
            if inserted_record:
                print("Insert succeeded:", inserted_record)
            return inserted_record
        except IntegrityError as e: # 중복 키 에러
            db.rollback()
            raise HTTPException(status_code=500, detail="Duplicate Key error. already exists.")
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    # UPDATE 쿼리 실행
    #Upsert는 **"Update"**와 **"Insert"**의 조합으로, 데이터베이스에 레코드가 존재하면 업데이트하고, 존재하지 않으면 삽입하는 작업을 의미합니다
    def execute_update(self, db: Session, query: str, params: dict = None):
        try:
            result = db.execute(text(query), params).mappings()
            updated_record = None
            updated_record = result.all()
            db.commit()
            if updated_record:
                print("Update succeeded:", updated_record)
            return updated_record
        except SQLAlchemyError as e:
            db.rollback()
            raise e
    
    # UPSERT 쿼리 실행
    def execute_upsert(self, db: Session, query: str, params: dict = None):
        try:
            result = db.execute(text(query), params).mappings()
            upserted_record = None
            upserted_record = result.all()
            db.commit()
            if upserted_record:
                print("Upsert succeeded:", upserted_record)
            return upserted_record
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    # DELETE 쿼리 실행
    def execute_delete(self, db: Session, query: str, params: dict = None):
        try:
            result = db.execute(text(query), params).mappings()
            deleted_record = None
            deleted_record = result.all()
            db.commit()
            if deleted_record:
                print("Delete succeeded:", deleted_record)
                return deleted_record
            else:
                # 삭제할 데이터가 존재하지 않을 때
                raise HTTPException(status_code=404, detail="No data to delete")
        except SQLAlchemyError as e:
            db.rollback()
            raise e