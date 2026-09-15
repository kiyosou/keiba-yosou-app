from fastapi import APIRouter
from sqlmodel import SQLModel

from database import engine

router = APIRouter()

@router.get("/dev/reset-db")
def reset_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    return {"message": "データベースをリセットしました"}