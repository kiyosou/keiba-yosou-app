from sqlmodel import SQLModel, Field

class Race(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_name: str
    date: str
    venue: str
    race_number: int
    surface: str
    distance: int
    weather: str
    track_condition: str

class Horse(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_id: int = Field(foreign_key="race.id")
    name: str
    running_style: str = ""
    memo_tag: str = ""
    past_performance_score: float = 0.0
    course_aptitude_score: float = 0.0
    pace_score: float = 0.0
    odds: float | None = None

class RaceResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_id: int = Field(foreign_key="race.id")
    first_place: str
    second_place: str
    third_place: str
    hit_umaren: bool = False
    hit_umatan: bool = False
    hit_sanrenpuku: bool = False
    review_memo: str = ""  # 回顧メモ
    

class FavoriteHorse(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    horse_name: str
    note: str = ""

class TrackBias(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: str
    venue: str
    turf_bias: str = ""
    dirt_bias: str = ""

class ActualResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_id: int = Field(foreign_key="race.id")
    horse_name: str
    finish_position: int
    time: str = ""
    corner_positions: str = ""
    final_3f: str = ""
    weight: str = ""