from sqlmodel import Session
from database import engine
from scoring import calculate_auto_score_from_history

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from database import engine
from models import Horse
from templates import templates
from parsing import parse_shutsuba_text

router = APIRouter()

@router.get("/horses/paste-import/{race_id}")
def paste_import_page(request: Request, race_id: int):
    return templates.TemplateResponse("horse_paste_import.html", {
        "request": request, "race_id": race_id, "entries": None, "raw_text": "",
    })

@router.post("/horses/paste-import/{race_id}")
def paste_import_parse(request: Request, race_id: int, raw_text: str = Form(...)):
    entries = parse_shutsuba_text(raw_text)

    with Session(engine) as session:
        for e in entries:
            auto = calculate_auto_score_from_history(session, e["name"])
            e["auto_score"] = auto["score"]
            e["auto_score_available"] = auto["available"]
            e["auto_score_samples"] = auto["sample_count"]

    return templates.TemplateResponse("horse_paste_import.html", {
        "request": request, "race_id": race_id, "entries": entries, "raw_text": raw_text,
    })

@router.post("/horses/bulk-add/{race_id}")
async def bulk_add_horses(race_id: int, request: Request):
    form = await request.form()
    count = int(form.get("count", 0))

    with Session(engine) as session:
        for i in range(count):
            name = form.get(f"name_{i}")
            if not name:
                continue
            odds_raw = form.get(f"odds_{i}") or ""
            waku_raw = form.get(f"waku_{i}") or ""
            umaban_raw = form.get(f"umaban_{i}") or ""
            horse = Horse(
                race_id=race_id,
                name=name,
                waku=int(waku_raw) if waku_raw else None,
                umaban=int(umaban_raw) if umaban_raw else None,
                running_style=form.get(f"running_style_{i}", ""),
                memo_tag=form.get(f"memo_tag_{i}", ""),
                past_performance_score=float(form.get(f"past_performance_score_{i}") or 0),
                course_aptitude_score=float(form.get(f"course_aptitude_score_{i}") or 0),
                pace_score=float(form.get(f"pace_score_{i}") or 0),
                odds=float(odds_raw) if odds_raw else None,
            )
            session.add(horse)
        session.commit()
    return RedirectResponse(url=f"/horses/ranking-page/{race_id}", status_code=303)