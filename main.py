from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from database import create_db_and_tables
from templates import templates
from routers import races, horses, results, favorites, dev, standard_times

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

app.include_router(races.router)
app.include_router(horses.router)
app.include_router(results.router)
app.include_router(favorites.router)
app.include_router(dev.router)
app.include_router(standard_times.router)