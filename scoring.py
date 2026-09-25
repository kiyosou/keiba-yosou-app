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
from parsing import infer_age_and_class, time_str_to_seconds, infer_class

def calculate_race_level(session, race, actual_time_str: str) -> dict:
    age, race_class = infer_age_and_class(race.race_name)
    standard = session.exec(
        select(StandardTime).where(
            StandardTime.venue == race.venue,
            StandardTime.surface == race.surface,
            StandardTime.distance == race.distance,
            StandardTime.course_type == (race.course_type or ""),
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

def calculate_auto_score_from_history(session, horse_name: str) -> dict:
    from models import ActualResult, Race

    results = session.exec(select(ActualResult).where(ActualResult.horse_name == horse_name)).all()

    dated_results = []
    for r in results:
        race = session.get(Race, r.race_id)
        if race:
            dated_results.append((race.date, r, race))
    dated_results.sort(key=lambda x: x[0], reverse=True)

    recent = dated_results[:3]

    diffs = []
    for date, r, race in recent:
        if not r.time:
            continue
        level = calculate_race_level(session, race, r.time)
        if level["available"]:
            diffs.append(level["diff_seconds"])

    if not diffs:
        return {"available": False, "score": 5.0, "sample_count": 0}

    avg_diff = sum(diffs) / len(diffs)
    score = 5.0 + avg_diff * 4.0
    score = max(0.0, min(10.0, round(score, 1)))

    return {"available": True, "score": score, "sample_count": len(diffs), "avg_diff": round(avg_diff, 2)}

def calculate_score_from_past_races(session, past_races: list[dict], age_category: str) -> dict:
    diffs = []
    for pr in past_races:
        race_class = infer_class(pr["race_class_text"])
        standard = session.exec(
            select(StandardTime).where(
                StandardTime.venue == pr["venue"],
                StandardTime.surface == pr["surface"],
                StandardTime.distance == pr["distance"],
                StandardTime.age == age_category,
                StandardTime.race_class == race_class,
            )
        ).first()
        if standard and standard.winner_time_seconds:
            diffs.append(standard.winner_time_seconds - pr["time_seconds"])

    if not diffs:
        return {"available": False, "score": 5.0, "sample_count": 0}

    avg_diff = sum(diffs) / len(diffs)
    score = max(0.0, min(10.0, round(5.0 + avg_diff * 4.0, 1)))
    return {"available": True, "score": score, "sample_count": len(diffs)}