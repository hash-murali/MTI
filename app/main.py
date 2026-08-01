from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import ConsumptionRecord, Evaluation, InteractionEvent, MediaItem, PreferenceDimension, RecommendationRun
from .recommender import ensure_default_profile, recommend, update_profile_from_evaluation
from .schemas import FeedbackPayload, OnboardingPayload, RecommendationContext
from .seed import seed_catalog

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    from .database import SessionLocal
    with SessionLocal() as db:
        seed_catalog(db)
        ensure_default_profile(db)
    yield


app = FastAPI(title="Personal AI Taste Intelligence System", version="1.0.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/catalog")
def catalog(media_type: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(MediaItem)
    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    items = list(db.scalars(stmt.order_by(MediaItem.title)))
    if q:
        ql = q.lower()
        items = [m for m in items if ql in m.title.lower() or any(ql in t.lower() for t in m.tags)]
    statuses = {r.media_id: r.status for r in db.scalars(select(ConsumptionRecord))}
    return [{"id":m.id,"title":m.title,"media_type":m.media_type,"language":m.language,"status":m.status,"runtime_minutes":m.runtime_minutes,"commitment":m.commitment,"tags":m.tags,"features":m.features,"user_status":statuses.get(m.id)} for m in items]


@app.post("/api/onboarding")
def onboarding(payload: OnboardingPayload, db: Session = Depends(get_db)):
    for answer in payload.answers:
        pref = db.scalar(select(PreferenceDimension).where(PreferenceDimension.scope == answer.scope, PreferenceDimension.feature == answer.feature))
        if pref is None:
            pref = PreferenceDimension(scope=answer.scope, feature=answer.feature)
            db.add(pref)
        pref.preferred_value = answer.value
        pref.importance = answer.importance
        pref.confidence = max(pref.confidence, .65)
        pref.explicit = True
        pref.evidence_count += 1
    db.add(InteractionEvent(event_type="onboarding_updated", payload={"count": len(payload.answers)}))
    db.commit()
    return {"saved": len(payload.answers)}


@app.get("/api/profile")
def profile(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(PreferenceDimension).order_by(PreferenceDimension.scope, PreferenceDimension.feature)))
    return [{"scope":p.scope,"feature":p.feature,"preferred_value":round(p.preferred_value*100),"importance":round(p.importance*100),"confidence":round(p.confidence*100),"evidence_count":p.evidence_count,"explicit":p.explicit} for p in rows]


@app.post("/api/media/{media_id}/feedback")
def feedback(media_id: int, payload: FeedbackPayload, db: Session = Depends(get_db)):
    item = db.get(MediaItem, media_id)
    if not item:
        raise HTTPException(404, "Media item not found")
    record = db.scalar(select(ConsumptionRecord).where(ConsumptionRecord.media_id == media_id))
    if record is None:
        record = ConsumptionRecord(media_id=media_id)
        db.add(record)
    record.status = payload.status
    record.progress = payload.progress
    record.reason = payload.reason
    db.add(InteractionEvent(event_type="feedback_submitted", media_id=media_id, payload=payload.model_dump()))
    evaluation = None
    if payload.enjoyment is not None and payload.quality is not None:
        evaluation = Evaluation(media_id=media_id, enjoyment=payload.enjoyment, quality=payload.quality, rewatch_value=payload.rewatch_value, aspects=payload.aspects, notes=payload.notes)
        db.add(evaluation)
        db.flush()
        update_profile_from_evaluation(db, item, evaluation)
    db.commit()
    return {"saved": True, "profile_updated": evaluation is not None}


@app.post("/api/recommendations")
def recommendations(context: RecommendationContext, db: Session = Depends(get_db)):
    return recommend(db, context)


@app.post("/api/recommendations/{media_id}/event")
def recommendation_event(media_id: int, event_type: str, db: Session = Depends(get_db)):
    if db.get(MediaItem, media_id) is None:
        raise HTTPException(404, "Media item not found")
    db.add(InteractionEvent(event_type=f"recommendation_{event_type}", media_id=media_id))
    db.commit()
    return {"saved": True}


@app.get("/api/analytics")
def analytics(db: Session = Depends(get_db)):
    consumption = list(db.scalars(select(ConsumptionRecord)))
    evaluations = list(db.scalars(select(Evaluation)))
    runs = list(db.scalars(select(RecommendationRun)))
    return {
        "tracked_items": len(consumption),
        "completed": sum(1 for x in consumption if x.status == "completed"),
        "abandoned": sum(1 for x in consumption if x.status == "abandoned"),
        "evaluations": len(evaluations),
        "recommendation_runs": len(runs),
        "average_enjoyment": round(sum(x.enjoyment for x in evaluations) / len(evaluations), 1) if evaluations else None,
    }


@app.get("/api/export")
def export_data(db: Session = Depends(get_db)):
    media = list(db.scalars(select(MediaItem)))
    consumption = list(db.scalars(select(ConsumptionRecord)))
    evaluations = list(db.scalars(select(Evaluation)))
    preferences = list(db.scalars(select(PreferenceDimension)))
    events = list(db.scalars(select(InteractionEvent)))
    return {
        "version": "1.0",
        "media": [{"id":m.id,"title":m.title,"media_type":m.media_type,"tags":m.tags,"features":m.features} for m in media],
        "consumption": [{"media_id":x.media_id,"status":x.status,"progress":x.progress,"reason":x.reason} for x in consumption],
        "evaluations": [{"media_id":x.media_id,"enjoyment":x.enjoyment,"quality":x.quality,"rewatch_value":x.rewatch_value,"aspects":x.aspects,"notes":x.notes} for x in evaluations],
        "preferences": [{"scope":x.scope,"feature":x.feature,"preferred_value":x.preferred_value,"importance":x.importance,"confidence":x.confidence,"evidence_count":x.evidence_count,"explicit":x.explicit} for x in preferences],
        "events": [{"event_type":x.event_type,"media_id":x.media_id,"payload":x.payload,"created_at":x.created_at.isoformat()} for x in events],
    }
