"""LOOPER API — Pydantic Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class OnboardUserRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    mobile_number: str = Field(..., pattern=r"^(0\d{9}|\+61\d{9})$")  # AU format
    interest_category: Optional[str] = Field(None, max_length=100)
    user_type: Optional[str] = "local"  # local, tourist, business
    preferred_language: Optional[str] = "en"


class OnboardUserResponse(BaseModel):
    user_id: int
    first_name: str
    join_code: str
    message: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: Optional[float] = 5.0
    category: Optional[str] = None
    limit: Optional[int] = 5


class SearchResult(BaseModel):
    business_id: int
    name: str
    category: str
    address: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    review_count: int
    avg_rating: Optional[float]
    top_review: Optional[str]  # most recent helpful review excerpt
    distance_km: Optional[float]


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    message: str  # contextual message from LOOPER
    total_results: int


class SubmitReviewRequest(BaseModel):
    business_id: int
    user_id: int
    rating: int = Field(..., ge=1, le=5)
    review_text: str = Field(..., min_length=10, max_length=2000)
    verified_visit: bool = False


class MapPinRequest(BaseModel):
    user_id: int
    pin_type: str  # offering, looking_for, event, alert
    title: str
    description: Optional[str]
    lat: float
    lng: float
    category: Optional[str]
    expires_in_days: Optional[int] = 30


class MapPinResponse(BaseModel):
    pin_id: int
    title: str
    pin_type: str
    lat: float
    lng: float
    created_at: datetime


class TouristInfoResponse(BaseModel):
    attractions: List[dict]
    transport: dict
    emergency: dict
    weather_summary: Optional[str]


class TrainingExportResponse(BaseModel):
    records_exported: int
    file_path: str
    format: str  # jsonl, parquet, etc.