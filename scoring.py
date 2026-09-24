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

from models import StandardTime
from parsing import infer_age_and_class, time_str_to_seconds

def calculate_race_level(session, race, actual_time_str: str) -> dict:
    age, race_class = infer_age_and_class(race.race_name)
    standard = session.exec(
        select(StandardTime).where(
            StandardTime.venue == race.venue,
            StandardTime.surface == race.surface,
            StandardTime.distance == race.distance,
            StandardTime.age == age,
            StandardTime.race_class == race_class,
        )
    ).first()

    if not standard or not standard.winner_time_seconds:
        return {"available": False, "age": age, "race_class": race_class}

    actual_seconds = time_str_to_seconds(actual_time_str)
    if not actual_seconds:
        return {"available": False, "age": age, "race_class": race_class}

    diff = standard.winner_time_seconds - actual_seconds  # プラス=基準より速い(レベルが高い)
    return {
        "available": True,
        "age": age,
        "race_class": race_class,
        "standard_time": standard.winner_time,
        "actual_time": actual_time_str,
        "diff_seconds": round(diff, 2),
    }