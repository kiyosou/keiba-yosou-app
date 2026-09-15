from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import Race, RaceResult, Horse
from scoring import race_label, get_predicted_ranking
from templates import templates

router = APIRouter()

@router.get("/results/input")
def result_input_page(request: Request):
    with Session(engine) as session:
        races = session.exec(select(Race)).all()
    race_options = [{"id": r.id, "label": race_label(r)} for r in races]
    return templates.TemplateResponse("result_input.html", {"request": request, "race_options": race_options})

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
def results_stats(request: Request, sort: str = "date", filter: str = "all"):
    with Session(engine) as session:
        results = session.exec(select(RaceResult)).all()
        result_list = []
        for r in results:
            race = session.get(Race, r.race_id)
            result_list.append({
                "race_label": race_label(race) if race else "不明なレース",
                "race_date": race.date if race else "",
                "first_place": r.first_place, "second_place": r.second_place, "third_place": r.third_place,
                "hit_umaren": r.hit_umaren, "hit_umatan": r.hit_umatan, "hit_sanrenpuku": r.hit_sanrenpuku,
                "review_memo": r.review_memo,
            })

    total = len(results)
    umaren_hits = sum(1 for r in results if r.hit_umaren)
    umatan_hits = sum(1 for r in results if r.hit_umatan)
    sanrenpuku_hits = sum(1 for r in results if r.hit_sanrenpuku)

    def rate(hits: int) -> float:
        return round(hits / total * 100, 1) if total > 0 else 0.0

    if filter == "hit":
        result_list = [r for r in result_list if r["hit_umaren"] or r["hit_umatan"] or r["hit_sanrenpuku"]]

    result_list.sort(key=lambda r: r["race_date"], reverse=(sort == "date"))

    return templates.TemplateResponse("stats.html", {
        "request": request, "results": result_list, "total": total,
        "umaren_hits": umaren_hits, "umaren_rate": rate(umaren_hits),
        "umatan_hits": umatan_hits, "umatan_rate": rate(umatan_hits),
        "sanrenpuku_hits": sanrenpuku_hits, "sanrenpuku_rate": rate(sanrenpuku_hits),
        "sort": sort, "filter": filter,
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