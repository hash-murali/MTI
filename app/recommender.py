from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ConsumptionRecord, Evaluation, MediaItem, PreferenceDimension, RecommendationRun
from .schemas import RecommendationContext

DEFAULT_PROFILE = {
    "philosophical_depth": (.78, .9),
    "narrative_complexity": (.78, .85),
    "world_building": (.8, .85),
    "emotional_intensity": (.65, .55),
    "scientific_grounding": (.82, .8),
    "pacing": (.58, .45),
    "darkness": (.58, .35),
    "originality": (.85, .85),
    "information_density": (.82, .85),
    "technical_depth": (.8, .8),
    "visual_explanation": (.72, .5),
}


def ensure_default_profile(db: Session) -> None:
    existing = {p.feature for p in db.scalars(select(PreferenceDimension).where(PreferenceDimension.scope == "global"))}
    for feature, (value, importance) in DEFAULT_PROFILE.items():
        if feature not in existing:
            db.add(PreferenceDimension(feature=feature, preferred_value=value, importance=importance, confidence=.12, scope="global"))
    db.commit()


def profile_for(db: Session, media_type: str) -> dict[str, PreferenceDimension]:
    global_rows = list(db.scalars(select(PreferenceDimension).where(PreferenceDimension.scope == "global")))
    scoped_rows = list(db.scalars(select(PreferenceDimension).where(PreferenceDimension.scope == media_type)))
    profile = {p.feature: p for p in global_rows}
    profile.update({p.feature: p for p in scoped_rows})
    return profile


def _match(feature_value: float, preferred: float) -> float:
    return max(0.0, 1.0 - abs(feature_value - preferred))


def _confidence(profile: dict[str, PreferenceDimension], features: dict[str, float]) -> float:
    relevant = [profile[k].confidence for k in features if k in profile]
    if not relevant:
        return .18
    evidence = sum(relevant) / len(relevant)
    metadata = min(1.0, len(features) / 8)
    return min(.95, .15 + .65 * evidence + .2 * metadata)


def _category(item: MediaItem, score: float, confidence: float, novelty: float, exploration: float) -> str:
    if item.quality_prior >= .94 and score >= .66:
        return "Masterpiece"
    if item.hidden_gem and score >= .67:
        return "Hidden Gem"
    if novelty > .72 and exploration >= .55:
        return "Wildcard"
    if novelty > .48:
        return "Adjacent Exploration"
    if score >= .82 and confidence >= .48:
        return "Likely Favorite"
    return "Safe Pick"


def recommend(db: Session, context: RecommendationContext) -> list[dict[str, Any]]:
    consumed = {r.media_id: r.status for r in db.scalars(select(ConsumptionRecord))}
    candidates = list(db.scalars(select(MediaItem)))
    output: list[dict[str, Any]] = []

    for item in candidates:
        if consumed.get(item.id) in {"completed", "rejected"}:
            continue
        if context.media_types and item.media_type not in context.media_types:
            continue
        if context.language and item.language.lower() != context.language.lower():
            continue
        if context.dub_required and item.media_type == "anime" and not item.dub_available:
            continue
        if context.completed_only and item.status != "completed":
            continue
        if context.time_available and item.runtime_minutes and item.runtime_minutes > context.time_available:
            continue

        profile = profile_for(db, item.media_type)
        weighted = 0.0
        total_weight = 0.0
        reasons: list[tuple[float, str]] = []
        risks: list[tuple[float, str]] = []

        for feature, value in item.features.items():
            pref = profile.get(feature)
            if not pref:
                continue
            weight = pref.importance * (.5 + .5 * pref.confidence)
            match = _match(value, pref.preferred_value)
            weighted += match * weight
            total_weight += weight
            contribution = match * weight
            if contribution >= .38:
                reasons.append((contribution, f"Strong {feature.replace('_', ' ')} match"))
            elif match < .48 and weight > .35:
                risks.append((weight * (1-match), f"Its {feature.replace('_', ' ')} may not match your current profile"))

        aspect_match = weighted / total_weight if total_weight else .5
        topic_match = min(1.0, len(set(item.tags) & {"technology","engineering","AI","mathematics","physics","science","space","programming","philosophy","psychology","history","fantasy","strategy","time","logic"}) / 3)
        quality = item.quality_prior
        novelty = max(0.05, 1 - item.popularity)

        context_fit = .7
        if context.mode == "focus":
            context_fit = .45 * item.features.get("information_density", .4) + .35 * item.features.get("technical_depth", .4) + .2 * item.features.get("scientific_grounding", .4)
        elif context.mode == "comfort":
            context_fit = 1 - (.55 * item.features.get("darkness", .4) + .25 * item.features.get("narrative_complexity", .5))
        elif context.mode == "discovery":
            context_fit = .45 + .55 * novelty
        if context.energy == "low":
            context_fit *= 1 - .35 * item.features.get("information_density", .5)
        elif context.energy == "high":
            context_fit = min(1.0, context_fit + .1 * item.features.get("narrative_complexity", .5))

        exploration_value = novelty * context.exploration
        score = .48 * aspect_match + .13 * topic_match + .16 * context_fit + .14 * quality + .09 * exploration_value
        score = max(0, min(1, score))
        confidence = _confidence(profile, item.features)
        category = _category(item, score, confidence, novelty, context.exploration)

        reasons = sorted(reasons, reverse=True)[:3]
        if topic_match > .3:
            reasons.append((topic_match, "Connects with your intellectual interests"))
        if not reasons:
            reasons.append((.1, "Balanced match across your current taste profile"))

        downsides = list(item.downsides)
        downsides.extend(text for _, text in sorted(risks, reverse=True)[:1])

        output.append({
            "media_id": item.id,
            "title": item.title,
            "media_type": item.media_type,
            "language": item.language,
            "category": category,
            "predicted_enjoyment": round(score * 100),
            "confidence": round(confidence * 100),
            "commitment": item.commitment,
            "runtime_minutes": item.runtime_minutes,
            "dub_available": item.dub_available,
            "why": [text for _, text in reasons[:4]],
            "downsides": downsides[:3],
            "tags": item.tags,
            "score_breakdown": {
                "taste_match": round(aspect_match * 100),
                "topic_match": round(topic_match * 100),
                "context_fit": round(context_fit * 100),
                "quality_prior": round(quality * 100),
                "exploration_value": round(exploration_value * 100),
            },
        })

    output.sort(key=lambda x: x["predicted_enjoyment"], reverse=True)

    selected: list[dict[str, Any]] = []
    type_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    for row in output:
        if len(selected) >= context.limit:
            break
        if type_counts[row["media_type"]] >= 3 or category_counts[row["category"]] >= 3:
            continue
        selected.append(row)
        type_counts[row["media_type"]] += 1
        category_counts[row["category"]] += 1
    if len(selected) < context.limit:
        ids = {x["media_id"] for x in selected}
        selected.extend(x for x in output if x["media_id"] not in ids)[: context.limit - len(selected)]

    run = RecommendationRun(context=context.model_dump(), results=selected)
    db.add(run)
    db.commit()
    return selected


def update_profile_from_evaluation(db: Session, item: MediaItem, evaluation: Evaluation) -> None:
    sentiment = (evaluation.enjoyment - 50) / 50
    strength = min(1.0, abs(sentiment))
    scopes = ["global", item.media_type]
    for scope in scopes:
        for feature, media_value in item.features.items():
            explicit_aspect = evaluation.aspects.get(feature)
            target_signal = sentiment if explicit_aspect is None else (explicit_aspect - 50) / 50
            evidence_strength = strength * (.65 if scope == "global" else .9)
            if explicit_aspect is not None:
                evidence_strength = max(evidence_strength, min(1, abs(target_signal)))
            if evidence_strength < .05:
                continue
            pref = db.scalar(select(PreferenceDimension).where(PreferenceDimension.scope == scope, PreferenceDimension.feature == feature))
            if pref is None:
                pref = PreferenceDimension(scope=scope, feature=feature, preferred_value=.5, importance=.5, confidence=.1)
                db.add(pref)
                db.flush()
            learning_rate = .08 + .18 * evidence_strength
            desired = media_value if target_signal >= 0 else 1 - media_value
            pref.preferred_value = max(0, min(1, (1-learning_rate) * pref.preferred_value + learning_rate * desired))
            pref.confidence = min(.95, pref.confidence + .04 + .08 * evidence_strength)
            pref.importance = min(1, pref.importance + .02 * evidence_strength)
            pref.evidence_count += 1
    db.commit()
