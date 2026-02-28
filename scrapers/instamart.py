"""
Swiggy Instamart Scraper
------------------------
Swiggy uses lat/lng passed as query params and cookies.
Their internal API endpoints are well-structured.
"""

import asyncio
import json
import re
from typing import List
from playwright.async_api import async_playwright, Page
from models.schemas import ProductResult, StoreResult, Platform
import logging

logger = logging.getLogger(__name__)

SWIGGY_BASE = "https://www.swiggy.com/instamart"


async def scrape_instamart_products(query: str, lat: float, lng: float) -> List[ProductResult]:
    results: List[ProductResult] = []
    api_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
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

        async def handle_response(response):
            url = response.url
            if any(k in url for k in ["search", "instamart", "minis", "listing"]):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        api_data.append({"url": url, "data": body})
                except Exception:
                    pass

        page.on("response", handle_response)

        # Swiggy needs lat/lng in URL params
        url = f"{SWIGGY_BASE}?lat={lat}&lng={lng}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Handle location dialog
        try:
            allow_btn = page.locator("button:has-text('Allow'), button:has-text('Enable Location')").first
            if await allow_btn.is_visible(timeout=3000):
                await allow_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        # Search
        try:
            search = page.locator("input[placeholder*='Search'], [data-testid='search-input']").first
            await search.click(timeout=5000)
            await search.fill(query)
            await search.press("Enter")
            await asyncio.sleep(4)
        except Exception as e:
            logger.warning(f"Instamart search error: {e}")

        # Parse API responses
        for item in api_data:
            data = item["data"]
            try:
                # Swiggy Instamart search response paths
                products = (
                    data.get("data", {}).get("products", []) or
                    data.get("data", {}).get("widgets", [{}])[0].get("data", {}).get("products", []) or
                    []
                )
                # Also handle listing API format
                if not products:
                    groups = data.get("data", {}).get("groups", [])
                    for g in groups:
                        products.extend(g.get("results", []))

                for prod in products:
                    variations = prod.get("variations", [prod])
                    for v in variations:
                        name = v.get("display_name", prod.get("display_name", ""))
                        if not name:
                            continue
                        price = float(v.get("price", 0) or 0) / 100
                        mrp = float(v.get("mrp", price * 100) or 0) / 100

                        results.append(ProductResult(
                            platform=Platform.INSTAMART,
                            name=name,
                            price=round(price, 2),
                            original_price=round(mrp, 2) if mrp > price else None,
                            discount_percent=int(v.get("discount_percent", 0) or 0) or None,
                            quantity=v.get("quantity", ""),
                            image_url=v.get("images", [None])[0] if v.get("images") else None,
                            in_stock=v.get("is_available", True),
                            delivery_time_minutes=v.get("delivery_time_in_minutes", 15),
                            category=prod.get("category_details", {}).get("name", ""),
                        ))
            except Exception as e:
                logger.warning(f"Instamart parse error: {e}")

        # DOM fallback
        if not results:
            results = await _instamart_dom_fallback(page)

        await browser.close()
    return results


async def _instamart_dom_fallback(page: Page) -> List[ProductResult]:
    results = []
    try:
        cards = await page.query_selector_all("[class*='Product'], [data-testid*='product']")
        for card in cards[:20]:
            try:
                name_el = await card.query_selector("[class*='name'], [class*='title']")
                price_el = await card.query_selector("[class*='price']")
                img_el = await card.query_selector("img")

                name = await name_el.inner_text() if name_el else "Unknown"
                price_text = await price_el.inner_text() if price_el else "0"
                img_src = await img_el.get_attribute("src") if img_el else None
                price_num = float(re.sub(r"[^\d.]", "", price_text.split("\n")[0]) or 0)

                results.append(ProductResult(
                    platform=Platform.INSTAMART,
                    name=name.strip(),
                    price=price_num,
                    image_url=img_src,
                    delivery_time_minutes=15,
                ))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Instamart DOM fallback error: {e}")
    return results


async def scrape_instamart_stores(lat: float, lng: float) -> List[StoreResult]:
    stores = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
        )
        page = await context.new_page()
        store_data = []

        async def handle_response(response):
            url = response.url
            if "store" in url.lower() or "coverage" in url.lower():
                try:
                    body = await response.json()
                    store_data.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(f"{SWIGGY_BASE}?lat={lat}&lng={lng}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        for data in store_data:
            try:
                for s in data.get("data", {}).get("stores", []):
                    stores.append(StoreResult(
                        platform=Platform.INSTAMART,
                        store_name=s.get("name", "Instamart Store"),
                        store_id=str(s.get("id", "")),
                        delivery_time_minutes=s.get("delivery_time", 15),
                        lat=s.get("lat"),
                        lng=s.get("lng"),
                    ))
            except Exception:
                continue

        if not stores:
            stores.append(StoreResult(
                platform=Platform.INSTAMART,
                store_name="Swiggy Instamart (Nearest)",
                delivery_time_minutes=15,
                is_open=True,
            ))

        await browser.close()
    return stores
