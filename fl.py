from flask import Flask, request, jsonify
from flask_cors import CORS
from zp import ZeptoScraper, BlinktScraper, InstamartScraper
import time

app = Flask(__name__)
CORS(app)

# Cache system
CACHE_TIME = 300
cache = {}

@app.route('/api/compare', methods=['POST'])
def compare_prices():
    data = request.json
    product_name = data.get('product_name', '').strip()
    pincode = data.get('pincode', '').strip()
    
    if not product_name or not pincode:
        return jsonify({"error": "Product name and pincode required"}), 400
    
    # Check cache
    key = f"{product_name}_{pincode}"
    if key in cache and time.time() - cache[key][1] < CACHE_TIME:
        return jsonify({
            "product": product_name,
            "results": cache[key][0],
            "cached": True
        }), 200
    
    # Scrape all platforms
    all_results = []
    
    zepto = ZeptoScraper()
    all_results.extend(zepto.search_product(product_name, pincode))
    
    blinkit = BlinktScraper()
    all_results.extend(blinkit.search_product(product_name, pincode))
    
    instamart = InstamartScraper()
    all_results.extend(instamart.search_product(product_name, pincode))
    
    # Sort by price
    all_results.sort(key=lambda x: x['price'])
    
    # Cache results
    cache[key] = (all_results, time.time())
    
    return jsonify({
        "product": product_name,
        "results": all_results,
        "cached": False
    }), 200

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)