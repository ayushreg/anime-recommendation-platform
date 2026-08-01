from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnimeOut(BaseModel):
    id: int
    mal_id: int | None = None
    title: str
    title_english: str | None = None
    synopsis: str | None = None
    genres: str
    themes: str = ""
    studios: str = ""
    score: float | None = None
    scored_by: int = 0
    episodes: int | None = None
    status: str | None = None
    year: int | None = None
    image_url: str | None = None
    type: str | None = None
    popularity: int = 0

    model_config = {"from_attributes": True}


class AnimeListOut(BaseModel):
    total: int
    items: list[AnimeOut]


class RatingIn(BaseModel):
    anime_id: int
    score: float = Field(ge=1, le=10)


class RatingOut(BaseModel):
    anime_id: int
    score: float
    anime: AnimeOut | None = None

    model_config = {"from_attributes": True}


class RecommendationOut(BaseModel):
    anime: AnimeOut
    reason: str
    score: float
    method: str


class RecommendationsResponse(BaseModel):
    user_id: int | None
    cached: bool
    recommendations: list[RecommendationOut]


class StatsOut(BaseModel):
    anime_count: int
    user_count: int
    rating_count: int
    cache_backend: str
