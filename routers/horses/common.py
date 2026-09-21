from sqlmodel import Session, select
from models import Horse

def get_all_horse_names(session: Session) -> list[str]:
    horses = session.exec(select(Horse)).all()
    return sorted(set(h.name for h in horses))