from fastapi import APIRouter, Query, HTTPException
from models.schemas import SearchResponse, Platform
from scrapers.blinkit import scrape_blinkit_products
from scrapers.zepto import scrape_zepto_products
from scrapers.instamart import scrape_instamart_products
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search_products(
    query: str = Query(..., description="Product name to search", example="milk"),
    lat: float = Query(..., description="User latitude", example=28.6139),
    lng: float = Query(..., description="User longitude", example=77.2090),
    platforms: str = Query("all", description="Comma-separated: blinkit,zepto,instamart or 'all'"),
):
    """
    Search for a product across all platforms simultaneously.
    Pass user's GPS coordinates for location-specific results.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Determine which platforms to scrape
    if platforms == "all":
        active = [Platform.BLINKIT, Platform.ZEPTO, Platform.INSTAMART]
    else:
        active = [Platform(p.strip()) for p in platforms.split(",") if p.strip()]

    # Build tasks for selected platforms
    tasks = {}
    if Platform.BLINKIT in active:
        tasks[Platform.BLINKIT] = scrape_blinkit_products(query, lat, lng)
    if Platform.ZEPTO in active:
        tasks[Platform.ZEPTO] = scrape_zepto_products(query, lat, lng)
    if Platform.INSTAMART in active:
        tasks[Platform.INSTAMART] = scrape_instamart_products(query, lat, lng)

    # Run all scrapers in parallel
    task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    all_results = []
    errors = {}

    for platform, result in zip(tasks.keys(), task_results):
        if isinstance(result, Exception):
            logger.error(f"{platform} scrape failed: {result}")
            errors[platform.value] = str(result)
        else:
            all_results.extend(result)

    # Sort by price ascending
    all_results.sort(key=lambda x: x.price)

    return SearchResponse(
        query=query,
        lat=lat,
        lng=lng,
        results=all_results,
        errors=errors,
    )
