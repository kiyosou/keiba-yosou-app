from fastapi import APIRouter, Request, Query
from sqlmodel import Session, select

from database import engine
from models import Race, Horse
from scoring import race_label, calculate_score
from templates import templates

router = APIRouter()

@router.get("/horses/profile/{horse_name}")
def horse_profile(request: Request, horse_name: str):
    with Session(engine) as session:
        horses = session.exec(select(Horse).where(Horse.name == horse_name)).all()
        history = []
        for h in horses:
            race = session.get(Race, h.race_id)
            history.append({
                "race_id": h.race_id,
                "race_label": race_label(race) if race else "不明なレース",
                "race_date": race.date if race else "",
                "running_style": h.running_style,
                "memo_tag": h.memo_tag,
                "score": calculate_score(h),
                "odds": h.odds,
            })
        history.sort(key=lambda x: x["race_date"], reverse=True)

    return templates.TemplateResponse("horse_profile.html", {
        "request": request, "horse_name": horse_name, "history": history,
    })

@router.get("/horses")
def horses_list(request: Request, style: str = ""):
    with Session(engine) as session:
        horses = session.exec(select(Horse)).all()

        by_name = {}
        for h in horses:
            race = session.get(Race, h.race_id)
            race_date = race.date if race else ""
            entry = {
                "id": h.id,
                "name": h.name,
                "race_id": h.race_id,
                "race_label": race_label(race) if race else "不明なレース",
                "race_date": race_date,
                "running_style": h.running_style,
                "memo_tag": h.memo_tag,
                "score": calculate_score(h),
                "odds": h.odds,
            }
            if h.name not in by_name or race_date > by_name[h.name]["race_date"]:
                by_name[h.name] = entry

        horse_list = list(by_name.values())
        if style:
            horse_list = [h for h in horse_list if h["running_style"] == style]

    horse_list.sort(key=lambda x: x["race_date"], reverse=True)
    return templates.TemplateResponse("horses_list.html", {
        "request": request, "horses": horse_list, "style": style,
    })

@router.get("/horses/compare")
def horses_compare(request: Request, names: list[str] = Query(default=[])):
    if len(names) > 18:
        names = names[:18]

    with Session(engine) as session:
        horse_histories = []
        for name in names:
            horses = session.exec(select(Horse).where(Horse.name == name)).all()
            history = []
            for h in horses:
                race = session.get(Race, h.race_id)
                history.append({
                    "race_id": h.race_id,
                    "race_label": race_label(race) if race else "不明なレース",
                    "race_date": race.date if race else "",
                    "running_style": h.running_style,
                    "memo_tag": h.memo_tag,
                    "score": calculate_score(h),
                    "odds": h.odds,
                })
            history.sort(key=lambda x: x["race_date"], reverse=True)
            horse_histories.append({"name": name, "history": history})

    return templates.TemplateResponse("horses_compare.html", {
        "request": request, "horse_histories": horse_histories,
    })