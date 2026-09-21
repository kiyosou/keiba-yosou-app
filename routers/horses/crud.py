from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import Race, Horse
from scoring import race_label
from templates import templates
from .common import get_all_horse_names

router = APIRouter()

@router.get("/horses/new")
def horse_add_page(request: Request):
    with Session(engine) as session:
        races = session.exec(select(Race)).all()
        horse_names = get_all_horse_names(session)
    race_options = [{"id": r.id, "label": race_label(r)} for r in races]
    return templates.TemplateResponse("input.html", {
        "request": request, "race_options": race_options, "horse_names": horse_names,
    })

@router.post("/horses/add")
def add_horse(
    race_id: int = Form(...),
    name: str = Form(...),
    waku: int = Form(None),
    umaban: int = Form(None),
    running_style: str = Form(""),
    memo_tag: str = Form(""),
    past_performance_score: float = Form(...),
    course_aptitude_score: float = Form(...),
    pace_score: float = Form(...),
    odds: float = Form(None),
):
    horse = Horse(
        race_id=race_id, name=name,
        waku=waku, umaban=umaban,
        running_style=running_style, memo_tag=memo_tag,
        past_performance_score=past_performance_score,
        course_aptitude_score=course_aptitude_score,
        pace_score=pace_score,
        odds=odds,
    )
    with Session(engine) as session:
        session.add(horse)
        session.commit()
    return RedirectResponse(url="/", status_code=303)

@router.post("/horses/{horse_id}/delete")
def delete_horse(horse_id: int):
    with Session(engine) as session:
        horse = session.get(Horse, horse_id)
        if horse:
            race_id = horse.race_id
            session.delete(horse)
            session.commit()
        else:
            race_id = None
    return RedirectResponse(url=f"/horses/ranking-page/{race_id}", status_code=303)

@router.get("/horses/{horse_id}/edit")
def horse_edit_page(request: Request, horse_id: int):
    with Session(engine) as session:
        horse = session.get(Horse, horse_id)
        races = session.exec(select(Race)).all()
    race_options = [{"id": r.id, "label": race_label(r)} for r in races]
    return templates.TemplateResponse("horse_edit.html", {
        "request": request, "horse": horse, "race_options": race_options,
    })

@router.post("/horses/{horse_id}/edit")
def horse_edit_submit(
    horse_id: int,
    race_id: int = Form(...),
    name: str = Form(...),
    waku: int = Form(None),
    umaban: int = Form(None),
    running_style: str = Form(""),
    memo_tag: str = Form(""),
    past_performance_score: float = Form(...),
    course_aptitude_score: float = Form(...),
    pace_score: float = Form(...),
    odds: float = Form(None),
):
    with Session(engine) as session:
        horse = session.get(Horse, horse_id)
        if horse:
            horse.race_id = race_id
            horse.name = name
            horse.waku = waku
            horse.umaban = umaban
            horse.running_style = running_style
            horse.memo_tag = memo_tag
            horse.past_performance_score = past_performance_score
            horse.course_aptitude_score = course_aptitude_score
            horse.pace_score = pace_score
            horse.odds = odds
            session.add(horse)
            session.commit()
    return RedirectResponse(url=f"/horses/ranking-page/{race_id}", status_code=303)