# Media Taste Intelligence — Version 1 MVP

A private, local-first recommendation system that learns from onboarding answers, consumption status, ratings, aspect feedback, and recommendation outcomes.

## Included

- Adaptive taste onboarding
- Global and media-specific taste profiles
- Local SQLite database
- Curated starter catalog across movies, TV, anime, manga, manhwa, and YouTube
- Context-aware recommendations
- Safe Pick, Likely Favorite, Hidden Gem, Adjacent Exploration, Wildcard, and Masterpiece categories
- Explainable score, confidence, matching reasons, and possible downsides
- Consumption tracking and aspect-level feedback
- Taste-profile inspection
- Complete JSON export
- REST API documentation at `/docs`

## Run on macOS

```bash
git clone https://github.com/hash-murali/MTI.git
cd MTI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000

## Run tests

```bash
pytest -q
```

## Data location

By default the SQLite database is created at:

```text
data/taste_intelligence.db
```

Set `TASTE_DB_URL` to override it.

## Reset

Stop the server, delete `data/taste_intelligence.db`, and restart.

## Architecture decision

This is intentionally a modular monolith. The recommendation engine is deterministic and inspectable rather than LLM-dependent. It can later be extended with metadata APIs, embeddings, local language models, and importers without replacing the core data model.
