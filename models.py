from sqlmodel import SQLModel, Field

class Race(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_name: str
    date: str
    venue: str
    race_number: int
    surface: str
    course_type: str = ""  # 外・内など(該当しない競馬場は空文字のまま)
    distance: int
    weather: str
    track_condition: str

class Horse(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    race_id: int = Field(foreign_key="race.id")
    name: str
    waku: int | None = None
    umaban: int | None = None
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

class StandardTime(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    venue: str
    surface: str
    distance: int
    course_type: str = ""
    age: str
    race_class: str
    race_count: int = 0
    winner_time: str = ""
    winner_time_seconds: float = 0.0
    top3_avg_time: str = ""
    top3_avg_seconds: float = 0.0
    rpci: float = 0.0
    pci3: float = 0.0
    ave_3f: float = 0.0