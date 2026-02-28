from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class Platform(str, Enum):
    BLINKIT = "blinkit"
    ZEPTO = "zepto"
    INSTAMART = "instamart"


class ProductResult(BaseModel):
    platform: Platform
    name: str
    price: float
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    quantity: Optional[str] = None          # e.g., "500g", "1L"
    image_url: Optional[str] = None
    in_stock: bool = True
    delivery_time_minutes: Optional[int] = None
    category: Optional[str] = None


class StoreResult(BaseModel):
    platform: Platform
    store_name: str
    store_id: Optional[str] = None
    distance_km: Optional[float] = None
    delivery_time_minutes: Optional[int] = None
    is_open: bool = True
    lat: Optional[float] = None
    lng: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    lat: float
    lng: float
    results: List[ProductResult]
    errors: dict = {}          # platform -> error message if scrape failed


class StoreResponse(BaseModel):
    lat: float
    lng: float
    stores: List[StoreResult]
    errors: dict = {}
