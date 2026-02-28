from fastapi import APIRouter, Query
from models.schemas import StoreResponse
from scrapers.blinkit import scrape_blinkit_stores
from scrapers.zepto import scrape_zepto_stores
from scrapers.instamart import scrape_instamart_stores
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=StoreResponse)
async def get_nearby_stores(
    lat: float = Query(..., description="User latitude", example=28.6139),
    lng: float = Query(..., description="User longitude", example=77.2090),
):
    """
    Find all nearby dark stores across Blinkit, Zepto, and Instamart
    for the given user coordinates.
    """
    blinkit_task = scrape_blinkit_stores(lat, lng)
    zepto_task = scrape_zepto_stores(lat, lng)
    instamart_task = scrape_instamart_stores(lat, lng)

    results = await asyncio.gather(blinkit_task, zepto_task, instamart_task, return_exceptions=True)

    all_stores = []
    errors = {}

    platform_names = ["blinkit", "zepto", "instamart"]
    for name, result in zip(platform_names, results):
        if isinstance(result, Exception):
            logger.error(f"{name} store scrape failed: {result}")
            errors[name] = str(result)
        else:
            all_stores.extend(result)

    # Sort by delivery time
    all_stores.sort(key=lambda x: x.delivery_time_minutes or 999)

    return StoreResponse(
        lat=lat,
        lng=lng,
        stores=all_stores,
        errors=errors,
    )
