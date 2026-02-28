from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.search import router as search_router
from routes.stores import router as stores_router
import uvicorn

app = FastAPI(
    title="QuickCommerce Aggregator API",
    description="Scrapes Blinkit, Zepto & Swiggy Instamart in real-time",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api/v1/search", tags=["Search"])
app.include_router(stores_router, prefix="/api/v1/stores", tags=["Stores"])

@app.get("/")
async def root():
    return {"status": "ok", "message": "QuickCommerce Aggregator API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
