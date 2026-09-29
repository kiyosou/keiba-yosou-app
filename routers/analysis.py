from urllib.parse import quote

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session, select

from database import engine
from models import Race, ActualResult
from scoring import race_label
from templates import templates
from parsing import parse_result_table
from race_analysis import (
    analyze_race, parse_laps, save_race_laps, list_analyzable_races,
    extract_laps_from_result_text, detect_going, save_race_results, names_match_ratio,
)

router = APIRouter()


@router.get("/analysis")
def analysis_index(request: Request):
    with Session(engine) as session:
        races = list_analyzable_races(session)
    return templates.TemplateResponse("race_analysis_list.html", {
        "request": request, "races": races,
    })


@router.get("/analysis/{race_id}")
def race_analysis_page(request: Request, race_id: int):
    with Session(engine) as session:
        race = session.get(Race, race_id)
        if not race:
            return HTMLResponse("レースが見つかりません", status_code=404)
        label = race_label(race)
        data = analyze_race(session, race)

    q = request.query_params
    saved = int(q["saved"]) if q.get("saved", "").isdigit() else None
    return templates.TemplateResponse("race_analysis.html", {
        "request": request,
        "race_id": race_id,
        "race_label": label,
        "a": data,
        "lap_error": q.get("lap_error") == "1",
        "saved": saved,
        "laps_saved": q.get("laps") == "1",
        "going": q.get("going"),
        "mismatch": q.get("mismatch") == "1",
    })


@router.post("/analysis/{race_id}/laps")
def save_laps(race_id: int, lap_text: str = Form("")):
    laps = parse_laps(lap_text)
    with Session(engine) as session:
        if not session.get(Race, race_id):
            return RedirectResponse(url="/analysis", status_code=303)
        if not laps:
            return RedirectResponse(url=f"/analysis/{race_id}?lap_error=1", status_code=303)
        save_race_laps(session, race_id, laps)
    return RedirectResponse(url=f"/analysis/{race_id}", status_code=303)


@router.get("/analysis/{race_id}/paste")
def paste_page(request: Request, race_id: int):
    with Session(engine) as session:
        race = session.get(Race, race_id)
        if not race:
            return HTMLResponse("レースが見つかりません", status_code=404)
        has_results = session.exec(
            select(ActualResult).where(ActualResult.race_id == race_id)
        ).first() is not None
        label = race_label(race)
    return templates.TemplateResponse("race_analysis_paste.html", {
        "request": request, "race_id": race_id, "race_label": label,
        "has_results": has_results, "error": None, "raw_text": "",
    })


@router.post("/analysis/{race_id}/paste")
def paste_result(request: Request, race_id: int, raw_text: str = Form("")):
    """結果ページの着順表(とハロンタイム)を貼り付けると、登録してそのまま分析を表示する。"""
    entries = parse_result_table(raw_text)
    with Session(engine) as session:
        race = session.get(Race, race_id)
        if not race:
            return HTMLResponse("レースが見つかりません", status_code=404)

        if not entries:
            has_results = session.exec(
                select(ActualResult).where(ActualResult.race_id == race_id)
            ).first() is not None
            return templates.TemplateResponse("race_analysis_paste.html", {
                "request": request, "race_id": race_id, "race_label": race_label(race),
                "has_results": has_results, "raw_text": raw_text,
                "error": "着順の表を読み取れませんでした。結果ページの表(着順〜単勝人気の列)を選択してコピーし直してください。",
            })

        ratio = names_match_ratio(session, race_id, [e["name"] for e in entries])
        save_race_results(session, race_id, entries)

        laps = extract_laps_from_result_text(raw_text)
        if laps:
            save_race_laps(session, race_id, laps)

        going = detect_going(raw_text, race.surface)
        changed_going = None
        if going and going != race.track_condition:
            race.track_condition = going
            session.add(race)
            session.commit()
            changed_going = going

    params = [f"saved={len(entries)}"]
    if laps:
        params.append("laps=1")
    if changed_going:
        params.append("going=" + quote(changed_going))
    if ratio is not None and ratio < 0.5:
        params.append("mismatch=1")
    return RedirectResponse(url=f"/analysis/{race_id}?" + "&".join(params), status_code=303)