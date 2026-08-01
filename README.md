# Anime Recommendation Platform

Full-stack hybrid recommendation system for discovering anime at catalog scale.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, React Router, nginx |
| API | FastAPI, Uvicorn, Pydantic, JWT (python-jose), Passlib/bcrypt |
| ML / ranking | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD embeddings |
| Data | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Cache / limits | Redis 7 (response cache + fixed-window rate limits) |
| Observability | Prometheus metrics (`/metrics`), structured health checks |
| Workers | Background refit worker (TF-IDF + embedding index) |
| Infra | Docker Compose, GitHub Actions CI |

## Product

Helps viewers and collectors find what to watch next across ~12,000 titles using:

1. Lexical / TF-IDF search  
2. Dense semantic search (TF-IDF → TruncatedSVD)  
3. Hybrid personalized recommendations (content + collaborative filtering)  

Auth, ratings, and watchlists feed personalization. Redis caches hot queries and recommendation payloads.

## Quick start

```bash
docker compose up --build
```

- Web: http://localhost:3000  
- API docs: http://localhost:8000/docs  
- Metrics: http://localhost:8000/metrics  

Demo user: `demo@anime.app` / `demo1234`

## API highlights

- `GET /api/anime/search?q=&mode=hybrid|semantic|lexical`
- `GET /api/recommendations` (JWT)
- `POST /api/ratings` (JWT)
- `GET /api/anime/{id}/similar`
- `GET /api/health` · `GET /api/stats` · `GET /metrics`

## Development

```bash
docker compose up db redis -d
cd backend && pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
pytest -q   # from backend/
```

See `docs/ARCHITECTURE.md` for system design notes.
