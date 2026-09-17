from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import Race, Horse, RaceResult, TrackBias
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
def races_dates(request: Request, venue: str = "", surface: str = "", min_distance: str = "", max_distance: str = ""):
    with Session(engine) as session:
        races = session.exec(select(Race)).all()

    venues = sorted(set(r.venue for r in races))
    surfaces = sorted(set(r.surface for r in races))
    distances = sorted(set(r.distance for r in races))

    filtered = races
    if venue:
        filtered = [r for r in filtered if r.venue == venue]
    if surface:
        filtered = [r for r in filtered if r.surface == surface]
    if min_distance:
        filtered = [r for r in filtered if r.distance >= int(min_distance)]
    if max_distance:
        filtered = [r for r in filtered if r.distance <= int(max_distance)]

    dates = sorted(set(r.date for r in filtered), reverse=True)
    date_list = [{"date": d, "count": sum(1 for r in filtered if r.date == d)} for d in dates]

    return templates.TemplateResponse("race_dates.html", {
        "request": request, "dates": date_list,
        "venues": venues, "surfaces": surfaces, "distances": distances,
        "selected_venue": venue, "selected_surface": surface,
        "selected_min": min_distance, "selected_max": max_distance,
    })

@router.get("/races/{date}")
def races_by_date(
    request: Request, date: str, sort: str = "venue",
    venue: str = "", surface: str = "", min_distance: str = "", max_distance: str = "",
):
    with Session(engine) as session:
        races = session.exec(select(Race).where(Race.date == date)).all()

        all_venues = sorted(set(r.venue for r in races))
        all_surfaces = sorted(set(r.surface for r in races))
        all_distances = sorted(set(r.distance for r in races))

        filtered = races
        if venue:
            filtered = [r for r in filtered if r.venue == venue]
        if surface:
            filtered = [r for r in filtered if r.surface == surface]
        if min_distance:
            filtered = [r for r in filtered if r.distance >= int(min_distance)]
        if max_distance:
            filtered = [r for r in filtered if r.distance <= int(max_distance)]

        if sort == "venue":
            filtered = sorted(filtered, key=lambda r: (r.venue, r.race_number))
        else:
            filtered = sorted(filtered, key=lambda r: r.race_number)

        race_list = [{"id": r.id, "label": race_label(r)} for r in filtered]

        bias_venues = sorted(set(r.venue for r in races))
        venue_bias = {}
        for v in bias_venues:
            bias = session.exec(
                select(TrackBias).where(TrackBias.date == date, TrackBias.venue == v)
            ).first()
            venue_bias[v] = {
                "turf_bias": bias.turf_bias if bias else "",
                "dirt_bias": bias.dirt_bias if bias else "",
            }

    return templates.TemplateResponse("races.html", {
        "request": request, "races": race_list, "date": date, "venue_bias": venue_bias,
        "venues": all_venues, "surfaces": all_surfaces, "distances": all_distances,
        "selected_venue": venue, "selected_surface": surface,
        "selected_min": min_distance, "selected_max": max_distance,
    })

@router.post("/races/{race_id}/delete")
def delete_race(race_id: int):
    with Session(engine) as session:
        race = session.get(Race, race_id)
        date = race.date if race else None

        horses = session.exec(select(Horse).where(Horse.race_id == race_id)).all()
        for h in horses:
            session.delete(h)

        results = session.exec(select(RaceResult).where(RaceResult.race_id == race_id)).all()
        for r in results:
            session.delete(r)

        if race:
            session.delete(race)

        session.commit()
    return RedirectResponse(url=f"/races/{date}" if date else "/races", status_code=303)

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
        return RedirectResponse(url=f"/races/{date}", status_code=303)

@router.post("/races/{date}/bias/{venue}")
def save_track_bias(date: str, venue: str, turf_bias: str = Form(""), dirt_bias: str = Form("")):
    with Session(engine) as session:
        bias = session.exec(
            select(TrackBias).where(TrackBias.date == date, TrackBias.venue == venue)
        ).first()
        if bias:
            bias.turf_bias = turf_bias
            bias.dirt_bias = dirt_bias
        else:
            bias = TrackBias(date=date, venue=venue, turf_bias=turf_bias, dirt_bias=dirt_bias)
        session.add(bias)
        session.commit()
    return RedirectResponse(url=f"/races/{date}", status_code=303)