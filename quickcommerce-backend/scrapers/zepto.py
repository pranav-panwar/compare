"""
Zepto Scraper
-------------
Zepto is a React SPA. It passes location via headers and cookies.
We intercept their internal GraphQL / REST calls.
"""

import asyncio
import json
import re
from typing import List
from playwright.async_api import async_playwright, Page
from models.schemas import ProductResult, StoreResult, Platform
import logging

logger = logging.getLogger(__name__)

ZEPTO_BASE = "https://www.zeptonow.com"


async def scrape_zepto_products(query: str, lat: float, lng: float) -> List[ProductResult]:
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
            extra_http_headers={
                "x-latitude": str(lat),
                "x-longitude": str(lng),
            }
        )

        page = await context.new_page()

        # Intercept Zepto API / GraphQL responses
        async def handle_response(response):
            url = response.url
            if any(k in url for k in ["search", "catalog", "graphql", "product"]):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        api_data.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        await page.goto(ZEPTO_BASE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Handle location permission
        try:
            loc_btn = page.locator("button:has-text('Allow'), button:has-text('Use my location')").first
            if await loc_btn.is_visible(timeout=3000):
                await loc_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        # Search
        try:
            search = page.locator("input[placeholder*='Search'], input[type='search']").first
            await search.click(timeout=5000)
            await search.fill(query)
            await search.press("Enter")
            await asyncio.sleep(4)
        except Exception as e:
            logger.warning(f"Zepto search error: {e}")

        # Parse API data
        for data in api_data:
            try:
                # Zepto structure varies — try multiple paths
                items = (
                    data.get("data", {}).get("searchResults", {}).get("items", []) or
                    data.get("data", {}).get("products", []) or
                    data.get("products", []) or
                    data.get("items", [])
                )
                for item in items:
                    product = item.get("product", item)
                    name = product.get("name", "")
                    if not name:
                        continue

                    mrp = float(product.get("mrp", 0) or 0) / 100  # Zepto stores paise
                    price = float(product.get("discountedPrice", product.get("price", mrp)) or mrp)
                    if price > 1000 and mrp < 100:   # Likely already in rupees
                        price = price / 100
                    if mrp > 1000 and mrp > price * 10:
                        mrp = mrp / 100

                    discount = int(product.get("discountPercent", 0) or 0)

                    results.append(ProductResult(
                        platform=Platform.ZEPTO,
                        name=name,
                        price=round(price, 2),
                        original_price=round(mrp, 2) if mrp > price else None,
                        discount_percent=discount if discount > 0 else None,
                        quantity=product.get("unit", product.get("quantity", "")),
                        image_url=product.get("imageUrl", product.get("image", "")),
                        in_stock=product.get("available", product.get("inStock", True)),
                        delivery_time_minutes=product.get("deliveryTime", 10),
                        category=product.get("category", {}).get("name", "") if isinstance(product.get("category"), dict) else "",
                    ))
            except Exception as e:
                logger.warning(f"Zepto parse error: {e}")

        # DOM fallback
        if not results:
            results = await _zepto_dom_fallback(page)

        await browser.close()
    return results


async def _zepto_dom_fallback(page: Page) -> List[ProductResult]:
    results = []
    try:
        cards = await page.query_selector_all("[data-testid='product-card'], .product-card, [class*='ProductCard']")
        for card in cards[:20]:
            try:
                name_el = await card.query_selector("[class*='name'], [class*='title'], h3")
                price_el = await card.query_selector("[class*='price'], [class*='Price']")
                img_el = await card.query_selector("img")
                qty_el = await card.query_selector("[class*='weight'], [class*='quantity'], [class*='unit']")

                name = await name_el.inner_text() if name_el else "Unknown"
                price_text = await price_el.inner_text() if price_el else "0"
                img_src = await img_el.get_attribute("src") if img_el else None
                qty = await qty_el.inner_text() if qty_el else ""

                price_num = float(re.sub(r"[^\d.]", "", price_text.split("\n")[0]) or 0)

                results.append(ProductResult(
                    platform=Platform.ZEPTO,
                    name=name.strip(),
                    price=price_num,
                    quantity=qty.strip(),
                    image_url=img_src,
                    delivery_time_minutes=10,
                ))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Zepto DOM fallback error: {e}")
    return results


async def scrape_zepto_stores(lat: float, lng: float) -> List[StoreResult]:
    stores = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
            extra_http_headers={"x-latitude": str(lat), "x-longitude": str(lng)},
        )
        page = await context.new_page()
        store_data = []

        async def handle_response(response):
            if "store" in response.url.lower():
                try:
                    body = await response.json()
                    store_data.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(ZEPTO_BASE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        for data in store_data:
            try:
                for s in data.get("stores", []):
                    stores.append(StoreResult(
                        platform=Platform.ZEPTO,
                        store_name=s.get("name", "Zepto Store"),
                        store_id=str(s.get("id", "")),
                        distance_km=s.get("distance"),
                        delivery_time_minutes=s.get("deliveryTime", 10),
                        lat=s.get("lat"),
                        lng=s.get("lng"),
                    ))
            except Exception:
                continue

        if not stores:
            stores.append(StoreResult(
                platform=Platform.ZEPTO,
                store_name="Zepto (Nearest)",
                delivery_time_minutes=10,
                is_open=True,
            ))

        await browser.close()
    return stores
