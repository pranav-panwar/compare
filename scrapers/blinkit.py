"""
Blinkit Scraper
---------------
Blinkit uses lat/lng via cookies/localStorage + their internal API.
We intercept network requests made by the page to capture API responses
directly — much faster and more reliable than DOM scraping.
"""

import asyncio
import json
import re
from typing import List, Optional
from playwright.async_api import async_playwright, Page
from models.schemas import ProductResult, StoreResult, Platform
import logging

logger = logging.getLogger(__name__)

BLINKIT_BASE = "https://blinkit.com"


async def _set_location(page: Page, lat: float, lng: float):
    """Inject location into Blinkit via localStorage before page load."""
    await page.add_init_script(f"""
        window.localStorage.setItem('userLat', '{lat}');
        window.localStorage.setItem('userLng', '{lng}');
    """)


async def scrape_blinkit_products(query: str, lat: float, lng: float) -> List[ProductResult]:
    """Search Blinkit and return product results for given location."""
    results: List[ProductResult] = []
    api_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            viewport={"width": 390, "height": 844},
            locale="en-IN",
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
        )

        page = await context.new_page()

        # Intercept Blinkit's search API calls
        async def handle_response(response):
            if "api.blinkit.com/v2/search" in response.url or \
               "search/suggestions" in response.url:
                try:
                    body = await response.json()
                    api_data.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        await _set_location(page, lat, lng)

        # Navigate to Blinkit and search
        await page.goto(BLINKIT_BASE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Set location via geolocation prompt or input
        try:
            # Try clicking "Detect Location" if present
            detect_btn = page.locator("text=Detect my location").first
            if await detect_btn.is_visible(timeout=3000):
                await detect_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        # Open search and type query
        try:
            search_input = page.locator("input[type='search'], input[placeholder*='Search']").first
            await search_input.click(timeout=5000)
            await search_input.fill(query)
            await search_input.press("Enter")
            await asyncio.sleep(4)  # Wait for API calls to fire
        except Exception as e:
            logger.warning(f"Blinkit search input error: {e}")

        # Parse intercepted API responses
        for data in api_data:
            try:
                # Blinkit returns products inside objects like data.products.objects
                products = (
                    data.get("data", {}).get("objects", []) or
                    data.get("objects", []) or
                    data.get("products", {}).get("objects", [])
                )
                for p_obj in products:
                    # Each object may contain a "type" == "product"
                    item = p_obj if "name" in p_obj else p_obj.get("product", {})
                    if not item.get("name"):
                        continue

                    price = float(item.get("price", 0) or item.get("mrp", 0))
                    mrp = float(item.get("mrp", price))
                    discount = int(item.get("discount", 0))

                    results.append(ProductResult(
                        platform=Platform.BLINKIT,
                        name=item.get("name", ""),
                        price=price,
                        original_price=mrp if mrp > price else None,
                        discount_percent=discount if discount > 0 else None,
                        quantity=item.get("unit", item.get("quantity", "")),
                        image_url=item.get("image", {}).get("url") if isinstance(item.get("image"), dict) else item.get("image"),
                        in_stock=item.get("is_available", item.get("inStock", True)),
                        delivery_time_minutes=10,  # Blinkit default ~10 min
                        category=item.get("category_name", ""),
                    ))
            except Exception as e:
                logger.warning(f"Blinkit parse error: {e}")

        # Fallback: DOM scraping if API interception yielded nothing
        if not results:
            results = await _blinkit_dom_fallback(page, query)

        await browser.close()

    return results


async def _blinkit_dom_fallback(page: Page, query: str) -> List[ProductResult]:
    """Fallback DOM scraper for Blinkit product cards."""
    results = []
    try:
        cards = await page.query_selector_all("[data-test-id='plp-product'], .Product__UpdatedPlpProductContainer")
        for card in cards[:20]:
            try:
                name = await card.query_selector(".Product__UpdatedTitle, [class*='product-name']")
                price = await card.query_selector("[class*='price'], .Product__UpdatedPriceAndAtcContainer")
                img = await card.query_selector("img")
                qty = await card.query_selector("[class*='weight'], [class*='quantity']")

                name_text = await name.inner_text() if name else "Unknown"
                price_text = await price.inner_text() if price else "0"
                img_src = await img.get_attribute("src") if img else None
                qty_text = await qty.inner_text() if qty else ""

                # Extract numeric price
                price_num = float(re.sub(r"[^\d.]", "", price_text.split("\n")[0] or "0") or 0)

                results.append(ProductResult(
                    platform=Platform.BLINKIT,
                    name=name_text.strip(),
                    price=price_num,
                    quantity=qty_text.strip(),
                    image_url=img_src,
                    delivery_time_minutes=10,
                ))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Blinkit DOM fallback error: {e}")
    return results


async def scrape_blinkit_stores(lat: float, lng: float) -> List[StoreResult]:
    """Get nearby Blinkit dark stores for given coordinates."""
    stores = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
        )
        page = await context.new_page()

        store_data = []

        async def handle_response(response):
            if "store" in response.url.lower() or "location" in response.url.lower():
                try:
                    body = await response.json()
                    store_data.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(BLINKIT_BASE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        for data in store_data:
            try:
                store_list = data.get("stores", data.get("data", {}).get("stores", []))
                for s in store_list:
                    stores.append(StoreResult(
                        platform=Platform.BLINKIT,
                        store_name=s.get("name", "Blinkit Store"),
                        store_id=str(s.get("id", "")),
                        distance_km=s.get("distance"),
                        delivery_time_minutes=s.get("delivery_time", 10),
                        lat=s.get("lat"),
                        lng=s.get("lng"),
                    ))
            except Exception:
                continue

        if not stores:
            # Return a placeholder if we couldn't get actual store list
            stores.append(StoreResult(
                platform=Platform.BLINKIT,
                store_name="Blinkit (Nearest)",
                delivery_time_minutes=10,
                is_open=True,
            ))

        await browser.close()
    return stores
