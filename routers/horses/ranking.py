from fastapi import APIRouter, Request
from sqlmodel import Session, select

from database import engine
from models import Race, Horse
from scoring import race_label, calculate_score
from templates import templates

router = APIRouter()

@router.get("/horses/ranking-page/{race_id}")
def ranking_page(
    request: Request, race_id: int,
    back_date: str = "", venue: str = "", surface: str = "",
    min_distance: str = "", max_distance: str = "",
):
    with Session(engine) as session:
        race = session.get(Race, race_id)
        horses = session.exec(select(Horse).where(Horse.race_id == race_id)).all()
        ranked = sorted(horses, key=lambda h: calculate_score(h), reverse=True)
        horse_list = [
            {
                "id": h.id,
                "name": h.name,
                "waku": h.waku,
                "umaban": h.umaban,
                "score": calculate_score(h),
                "odds": h.odds,
                "running_style": h.running_style,
                "memo_tag": h.memo_tag,
            }
            for h in ranked
        ]

    back_url = ""
    if back_date:
        params = []
        if venue:
            params.append(f"venue={venue}")
        if surface:
            params.append(f"surface={surface}")
        if min_distance:
            params.append(f"min_distance={min_distance}")
        if max_distance:
            params.append(f"max_distance={max_distance}")
        back_url = f"/races/{back_date}" + ("?" + "&".join(params) if params else "")

    return templates.TemplateResponse("ranking.html", {
        "request": request, "horses": horse_list,
        "race_label": race_label(race) if race else "",
        "race_id": race_id, "back_url": back_url,
    })