# QuickCommerce Aggregator — Python Backend

Real-time scraper + REST API for **Blinkit, Zepto & Swiggy Instamart**.  
Runs scrapers in parallel, location-aware, deployable to Railway / Render for free.

---

## 📁 Project Structure

```
quickcommerce-backend/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── Dockerfile               # For containerized deployment
├── render.yaml              # Render.com config
├── railway.json             # Railway.app config
├── models/
│   └── schemas.py           # Pydantic response models
├── routes/
│   ├── search.py            # GET /api/v1/search
│   └── stores.py            # GET /api/v1/stores
└── scrapers/
    ├── blinkit.py
    ├── zepto.py
    └── instamart.py
```

---

## 🚀 API Endpoints

### 1. Search Products
```
GET /api/v1/search?query=milk&lat=28.6139&lng=77.2090
```

**Query params:**
| Param | Required | Description |
|-------|----------|-------------|
| `query` | ✅ | Product to search |
| `lat` | ✅ | User GPS latitude |
| `lng` | ✅ | User GPS longitude |
| `platforms` | ❌ | `all` (default) or `blinkit,zepto,instamart` |

**Response:**
```json
{
  "query": "milk",
  "lat": 28.6139,
  "lng": 77.2090,
  "results": [
    {
      "platform": "blinkit",
      "name": "Amul Taza Homogenised Toned Milk",
      "price": 28.0,
      "original_price": 32.0,
      "discount_percent": 12,
      "quantity": "500ml",
      "image_url": "https://...",
      "in_stock": true,
      "delivery_time_minutes": 10,
      "category": "Dairy"
    }
  ],
  "errors": {}
}
```

### 2. Nearby Stores
```
GET /api/v1/stores?lat=28.6139&lng=77.2090
```

**Response:**
```json
{
  "lat": 28.6139,
  "lng": 77.2090,
  "stores": [
    {
      "platform": "blinkit",
      "store_name": "Blinkit - Connaught Place",
      "distance_km": 1.2,
      "delivery_time_minutes": 9,
      "is_open": true
    }
  ],
  "errors": {}
}
```

### 3. Health Check
```
GET /health
```

---

## 🛠️ Local Development

```bash
# 1. Clone and install
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium

# 2. Run
python main.py
# or
uvicorn main:app --reload --port 8000

# 3. Test
curl "http://localhost:8000/api/v1/search?query=milk&lat=28.6139&lng=77.2090"
```

---

## ☁️ Deploy to Railway (Recommended)

1. Push this folder to a **GitHub repo**
2. Go to [railway.app](https://railway.app) → **New Project** → Deploy from GitHub
3. Select your repo — Railway detects `Dockerfile` automatically
4. Done! Get your public URL from the Railway dashboard

**Important:** Railway free tier gives **$5/month credit** which covers ~500 hours.  
For production, upgrade to Starter ($5/month) for always-on.

---

## ☁️ Deploy to Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect repo → Render detects `render.yaml`
4. Deploy — free tier spins down after 15 min inactivity (adds cold start delay)

---

## 📱 Android Integration (Kotlin)

### Retrofit Setup
```kotlin
// build.gradle
implementation("com.squareup.retrofit2:retrofit:2.9.0")
implementation("com.squareup.retrofit2:converter-gson:2.9.0")
implementation("com.google.android.gms:play-services-location:21.0.1")
```

### Data Classes
```kotlin
data class ProductResult(
    val platform: String,
    val name: String,
    val price: Double,
    val originalPrice: Double?,
    val discountPercent: Int?,
    val quantity: String?,
    val imageUrl: String?,
    val inStock: Boolean,
    val deliveryTimeMinutes: Int?,
    val category: String?
)

data class SearchResponse(
    val query: String,
    val lat: Double,
    val lng: Double,
    val results: List<ProductResult>,
    val errors: Map<String, String>
)
```

### API Interface
```kotlin
interface QuickCommerceApi {
    @GET("api/v1/search")
    suspend fun searchProducts(
        @Query("query") query: String,
        @Query("lat") lat: Double,
        @Query("lng") lng: Double,
        @Query("platforms") platforms: String = "all"
    ): SearchResponse

    @GET("api/v1/stores")
    suspend fun getNearbyStores(
        @Query("lat") lat: Double,
        @Query("lng") lng: Double
    ): StoreResponse
}

// Retrofit instance
val retrofit = Retrofit.Builder()
    .baseUrl("https://YOUR-APP.railway.app/")
    .addConverterFactory(GsonConverterFactory.create())
    .build()

val api = retrofit.create(QuickCommerceApi::class.java)
```

### Getting GPS in Compose
```kotlin
@Composable
fun SearchScreen() {
    val context = LocalContext.current
    val fusedLocation = LocationServices.getFusedLocationProviderClient(context)
    var lat by remember { mutableDoubleStateOf(0.0) }
    var lng by remember { mutableDoubleStateOf(0.0) }

    LaunchedEffect(Unit) {
        fusedLocation.lastLocation.addOnSuccessListener { location ->
            location?.let {
                lat = it.latitude
                lng = it.longitude
            }
        }
    }

    // Pass lat/lng to your ViewModel which calls the API
}
```

---

## ⚠️ Important Notes

### Anti-bot Measures
These platforms use Cloudflare and fingerprinting. If scraping gets blocked:
- Rotate user agents (add a `USER_AGENTS` list to scraper)
- Add random delays between actions (`asyncio.sleep(random.uniform(1, 3))`)
- Consider **residential proxies** for production (e.g., BrightData, Oxylabs)

### Rate Limiting
Add rate limiting to avoid hammering the same user's requests:
```python
# Add to requirements.txt: slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
# @limiter.limit("10/minute") on your routes
```

### Caching
For popular queries, cache results for 2-5 minutes:
```python
# Add: pip install cachetools
from cachetools import TTLCache
cache = TTLCache(maxsize=500, ttl=300)  # 5 min cache
```

### Legal Note
Web scraping may violate the Terms of Service of these platforms.
This is built for educational/personal project purposes.
