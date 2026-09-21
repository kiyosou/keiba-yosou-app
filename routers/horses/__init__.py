from fastapi import APIRouter

from .common import get_all_horse_names
from . import crud, ranking, csv_io, paste_import, profile

router = APIRouter()
router.include_router(crud.router)
router.include_router(ranking.router)
router.include_router(csv_io.router)
router.include_router(paste_import.router)
router.include_router(profile.router)