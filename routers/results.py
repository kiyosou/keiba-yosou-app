from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import Race, RaceResult, Horse, ActualResult
from scoring import race_label, get_predicted_ranking, calculate_race_level
from templates import templates
from parsing import parse_result_table
from routers.horses import get_all_horse_names

router = APIRouter()

@router.get("/results/input")
def result_input_page(request: Request):
    with Session(engine) as session:
        races = session.exec(select(Race)).all()
        horse_names = get_all_horse_names(session)
    race_options = [{"id": r.id, "label": race_label(r)} for r in races]
    return templates.TemplateResponse("result_input.html", {
        "request": request, "race_options": race_options, "horse_names": horse_names,
    })

@router.post("/results/add")
def add_result(
    race_id: int = Form(...),
    first_place: str = Form(...),
    second_place: str = Form(...),
    third_place: str = Form(...),
    review_memo: str = Form(""),
):
    with Session(engine) as session:
        ranking = get_predicted_ranking(race_id, session)
        hit_umaren = hit_umatan = hit_sanrenpuku = False

        if len(ranking) >= 2:
            top2 = ranking[:2]
            actual_top2 = {first_place, second_place}
            if set(top2) == actual_top2:
                hit_umaren = True
            if ranking[0] == first_place and ranking[1] == second_place:
                hit_umatan = True

        if len(ranking) >= 3:
            top3 = set(ranking[:3])
            actual_top3 = {first_place, second_place, third_place}
            if top3 == actual_top3:
                hit_sanrenpuku = True

        result = RaceResult(
            race_id=race_id, first_place=first_place,
            second_place=second_place, third_place=third_place,
            hit_umaren=hit_umaren, hit_umatan=hit_umatan, hit_sanrenpuku=hit_sanrenpuku,
            review_memo=review_memo,
        )   
        session.add(result)
        session.commit()
    return RedirectResponse(url="/results/input", status_code=303)

@router.get("/results/stats")
def results_stats(request: Request):
    with Session(engine) as session:
        results = session.exec(select(RaceResult)).all()

    total = len(results)
    umaren_hits = sum(1 for r in results if r.hit_umaren)
    umatan_hits = sum(1 for r in results if r.hit_umatan)
    sanrenpuku_hits = sum(1 for r in results if r.hit_sanrenpuku)

    def rate(hits: int) -> float:
        return round(hits / total * 100, 1) if total > 0 else 0.0

    return templates.TemplateResponse("stats.html", {
        "request": request, "total": total,
        "umaren_hits": umaren_hits, "umaren_rate": rate(umaren_hits),
        "umatan_hits": umatan_hits, "umatan_rate": rate(umatan_hits),
        "sanrenpuku_hits": sanrenpuku_hits, "sanrenpuku_rate": rate(sanrenpuku_hits),
    })

@router.get("/search")
def search_page(request: Request, q: str = ""):
    horse_matches = []
    memo_matches = []

    if q:
        with Session(engine) as session:
            horses = session.exec(select(Horse)).all()
            for h in horses:
                if q in h.name:
                    race = session.get(Race, h.race_id)
                    horse_matches.append({
                        "race_id": h.race_id,
                        "race_label": race_label(race) if race else "不明なレース",
                        "name": h.name,
                        "running_style": h.running_style,
                        "memo_tag": h.memo_tag,
                    })

            results = session.exec(select(RaceResult)).all()
            for r in results:
                if q in r.review_memo:
                    race = session.get(Race, r.race_id)
                    memo_matches.append({
                        "race_label": race_label(race) if race else "不明なレース",
                        "review_memo": r.review_memo,
                    })

    return templates.TemplateResponse("search.html", {
        "request": request, "q": q,
        "horse_matches": horse_matches, "memo_matches": memo_matches,
    })

@router.get("/results/list")
def results_list(
    request: Request,
    sort: str = "date",
    filter: str = "all",
    venue: str = "",
    min_distance: str = "",
    max_distance: str = "",
):
    with Session(engine) as session:
        results = session.exec(select(RaceResult)).all()
        result_list = []
        for r in results:
            race = session.get(Race, r.race_id)
            result_list.append({
                "race_label": race_label(race) if race else "不明なレース",
                "race_date": race.date if race else "",
                "venue": race.venue if race else "",
                "distance": race.distance if race else 0,
                "first_place": r.first_place, "second_place": r.second_place, "third_place": r.third_place,
                "hit_umaren": r.hit_umaren, "hit_umatan": r.hit_umatan, "hit_sanrenpuku": r.hit_sanrenpuku,
                "review_memo": r.review_memo,
            })

    # 絞り込みの選択肢は、実際に存在するデータからのみ作る
    venues = sorted(set(r["venue"] for r in result_list if r["venue"]))
    distances = sorted(set(r["distance"] for r in result_list if r["distance"]))

    if filter == "hit":
        result_list = [r for r in result_list if r["hit_umaren"] or r["hit_umatan"] or r["hit_sanrenpuku"]]

    if venue:
        result_list = [r for r in result_list if r["venue"] == venue]

    if min_distance:
        result_list = [r for r in result_list if r["distance"] >= int(min_distance)]

    if max_distance:
        result_list = [r for r in result_list if r["distance"] <= int(max_distance)]

    result_list.sort(key=lambda r: r["race_date"], reverse=(sort == "date"))

    return templates.TemplateResponse("results_list.html", {
        "request": request, "results": result_list, "sort": sort, "filter": filter,
        "venues": venues, "distances": distances,
        "selected_venue": venue, "selected_min": min_distance, "selected_max": max_distance,
    })

@router.get("/results/paste/{race_id}")
def result_paste_page(request: Request, race_id: int):
    return templates.TemplateResponse("result_paste.html", {
        "request": request, "race_id": race_id, "entries": None, "raw_text": "",
    })

@router.post("/results/paste/{race_id}")
def result_paste_parse(request: Request, race_id: int, raw_text: str = Form(...)):
    entries = parse_result_table(raw_text)
    return templates.TemplateResponse("result_paste.html", {
        "request": request, "race_id": race_id, "entries": entries, "raw_text": raw_text,
    })

@router.post("/results/paste-confirm/{race_id}")
async def result_paste_confirm(race_id: int, request: Request):
    form = await request.form()
    count = int(form.get("count", 0))

    with Session(engine) as session:
        race = session.get(Race, race_id)
        for i in range(count):
            name = form.get(f"name_{i}")
            if not name:
                continue
            actual = ActualResult(
                race_id=race_id,
                horse_name=name,
                finish_position=int(form.get(f"finish_position_{i}") or 0),
                time=form.get(f"time_{i}", ""),
                corner_positions=form.get(f"corner_positions_{i}", ""),
                final_3f=form.get(f"final_3f_{i}", ""),
                weight=form.get(f"weight_{i}", ""),
            )
            session.add(actual)
        session.commit()

        race_level = None
        winner_time = form.get("time_0", "")
        if race and winner_time:
            race_level = calculate_race_level(session, race, winner_time)

    return templates.TemplateResponse("result_paste_done.html", {
        "request": request, "race_id": race_id, "race_level": race_level,
    })