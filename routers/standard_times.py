from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from openpyxl import load_workbook
import io

from sqlmodel import Session, select
from database import engine
from models import StandardTime
from templates import templates
from parsing import time_str_to_seconds

router = APIRouter()

VENUES = ["札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉"]

@router.get("/standard-times/import")
def standard_time_import_page(request: Request):
    return templates.TemplateResponse("standard_time_import.html", {
        "request": request, "venues": VENUES,
    })

@router.post("/standard-times/import")
async def standard_time_import(venue: str = Form(...), file: UploadFile = File(...)):
    content = await file.read()
    workbook = load_workbook(io.BytesIO(content), data_only=True)

    imported_count = 0
    with Session(engine) as session:
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]

            # シート名(例: 芝1200, ダ1800)から馬場と距離を判定
            if sheet_name.startswith("芝"):
                surface = "芝"
                distance_str = sheet_name[1:]
            elif sheet_name.startswith("ダ"):
                surface = "ダート"
                distance_str = sheet_name[1:]
            else:
                continue

            if not distance_str.isdigit():
                continue
            distance = int(distance_str)

            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                age, race_class = row[0], row[1]
                if not age or not race_class:
                    continue

                race_count = row[2] or 0
                winner_time = str(row[4]) if row[4] else ""
                top3_avg_time = str(row[7]) if row[7] else ""
                pci3 = row[10] or 0
                ave_3f = row[11] or 0

                # 既存の同じ組み合わせがあれば削除してから登録(上書き更新)
                existing = session.exec(
                    select(StandardTime).where(
                        StandardTime.venue == venue,
                        StandardTime.surface == surface,
                        StandardTime.distance == distance,
                        StandardTime.age == age,
                        StandardTime.race_class == race_class,
                    )
                ).first()
                if existing:
                    session.delete(existing)
                    session.commit()

                st = StandardTime(
                    venue=venue, surface=surface, distance=distance,
                    age=age, race_class=race_class,
                    race_count=int(race_count) if race_count else 0,
                    winner_time=winner_time,
                    winner_time_seconds=time_str_to_seconds(winner_time),
                    top3_avg_time=top3_avg_time,
                    top3_avg_seconds=time_str_to_seconds(top3_avg_time),
                    pci3=float(pci3) if pci3 else 0.0,
                    ave_3f=float(ave_3f) if ave_3f else 0.0,
                )
                session.add(st)
                imported_count += 1
        session.commit()

    return RedirectResponse(url=f"/standard-times?imported={imported_count}", status_code=303)

@router.get("/standard-times")
def standard_times_list(request: Request):
    with Session(engine) as session:
        times = session.exec(select(StandardTime)).all()
    times_sorted = sorted(times, key=lambda t: (t.venue, t.surface, t.distance, t.age, t.race_class))
    return templates.TemplateResponse("standard_times.html", {
        "request": request, "times": times_sorted,
    })