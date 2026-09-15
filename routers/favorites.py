from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from database import engine
from models import FavoriteHorse
from templates import templates

router = APIRouter()

@router.get("/favorites")
def favorites_list(request: Request):
    with Session(engine) as session:
        favorites = session.exec(select(FavoriteHorse)).all()
    return templates.TemplateResponse("favorites.html", {"request": request, "favorites": favorites})

@router.post("/favorites/add")
def add_favorite(
    horse_name: str = Form(...),
    note: str = Form(""),
):
    with Session(engine) as session:
        favorite = FavoriteHorse(horse_name=horse_name, note=note)
        session.add(favorite)
        session.commit()
    return RedirectResponse(url="/favorites", status_code=303)

@router.post("/favorites/{favorite_id}/delete")
def delete_favorite(favorite_id: int):
    with Session(engine) as session:
        favorite = session.get(FavoriteHorse, favorite_id)
        if favorite:
            session.delete(favorite)
            session.commit()
    return RedirectResponse(url="/favorites", status_code=303)