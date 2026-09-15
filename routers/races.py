from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import Race, Horse, RaceResult
from scoring import race_label
from templates import templates

router = APIRouter()

@router.get("/races/add")
def race_add_page(request: Request):
    return templates.TemplateResponse("race_add.html", {"request": request})

@router.post("/races/add")
def add_race(
    race_name: str = Form(...),
    date: str = Form(...),
    venue: str = Form(...),
    race_number: int = Form(...),
    surface: str = Form(...),
    distance: int = Form(...),
    weather: str = Form(...),
    track_condition: str = Form(...),
):
    race = Race(
        race_name=race_name, date=date, venue=venue, race_number=race_number,
        surface=surface, distance=distance,
        weather=weather, track_condition=track_condition,
    )
    with Session(engine) as session:
        session.add(race)
        session.commit()
    return RedirectResponse(url="/", status_code=303)

@router.get("/races")
def races_list(request: Request, sort: str = "date"):
    with Session(engine) as session:
        races = session.exec(select(Race)).all()

    if sort == "venue":
        races = sorted(races, key=lambda r: (r.venue, r.date))
    else:
        races = sorted(races, key=lambda r: r.date, reverse=True)

    race_list = [{"id": r.id, "label": race_label(r)} for r in races]
    return templates.TemplateResponse("races.html", {
        "request": request, "races": race_list, "sort": sort,
    })

@router.post("/races/{race_id}/delete")
def delete_race(race_id: int):
    with Session(engine) as session:
        horses = session.exec(select(Horse).where(Horse.race_id == race_id)).all()
        for h in horses:
            session.delete(h)

        results = session.exec(select(RaceResult).where(RaceResult.race_id == race_id)).all()
        for r in results:
            session.delete(r)

        race = session.get(Race, race_id)
        if race:
            session.delete(race)

        session.commit()
    return RedirectResponse(url="/races", status_code=303)

@router.get("/races/{race_id}/edit")
def race_edit_page(request: Request, race_id: int):
    with Session(engine) as session:
        race = session.get(Race, race_id)
    return templates.TemplateResponse("race_edit.html", {"request": request, "race": race})

@router.post("/races/{race_id}/edit")
def race_edit_submit(
    race_id: int,
    race_name: str = Form(...),
    date: str = Form(...),
    venue: str = Form(...),
    race_number: int = Form(...),
    surface: str = Form(...),
    distance: int = Form(...),
    weather: str = Form(...),
    track_condition: str = Form(...),
):
    with Session(engine) as session:
        race = session.get(Race, race_id)
        if race:
            race.race_name = race_name
            race.date = date
            race.venue = venue
            race.race_number = race_number
            race.surface = surface
            race.distance = distance
            race.weather = weather
            race.track_condition = track_condition
            session.add(race)
            session.commit()
    return RedirectResponse(url="/races", status_code=303)
