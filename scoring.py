from sqlmodel import Session, select
from models import Horse, Race

def race_label(race: Race) -> str:
    return f"{race.date} {race.venue}{race.race_number}R {race.race_name}({race.surface}{race.distance}m)"

def calculate_score(horse: Horse) -> float:
    score = (
        horse.past_performance_score * 0.40 +
        horse.course_aptitude_score * 0.35 +
        horse.pace_score * 0.25
    )
    return round(score, 2)

def get_predicted_ranking(race_id: int, session: Session) -> list[str]:
    horses = session.exec(select(Horse).where(Horse.race_id == race_id)).all()
    ranked = sorted(horses, key=lambda h: calculate_score(h), reverse=True)
    return [h.name for h in ranked]