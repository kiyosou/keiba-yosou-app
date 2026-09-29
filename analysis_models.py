from sqlmodel import SQLModel, Field


class RaceLap(SQLModel, table=True):
    """レースごとのラップ(ハロンタイム)。分析ページから登録する。"""
    race_id: int = Field(primary_key=True)
    lap_times: str = ""


class StandardTimeExtra(SQLModel, table=True):
    """基準タイムの追加項目(全馬平均・ラップ平均)。StandardTimeと同じ条件で1行ずつ対応する。"""
    id: int | None = Field(default=None, primary_key=True)
    venue: str
    surface: str
    distance: int
    course_type: str = ""
    age: str
    race_class: str
    all_avg_seconds: float = 0.0
    lap_avg: str = ""