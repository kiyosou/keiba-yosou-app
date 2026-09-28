import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine

load_dotenv()

database_url = os.getenv("DATABASE_URL", "sqlite:///database.db")
engine = create_engine(database_url, pool_pre_ping=True)

def create_db_and_tables():
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"[警告] 起動時にデータベースへ接続できませんでした。ネットワークを確認してください: {e}")