from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

class ZeptoScraper:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in background
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    
    def search_product(self, product_name, pincode):
        try:
            url = f"https://www.zeptonow.com/search?q={product_name}"
            self.driver.get(url)
            
            wait = WebDriverWait(self.driver, 10)
            # IMPORTANT: Replace these selectors with actual ones from the website
            products = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "product-card"))
            )
            
            results = []
            for product in products[:5]:
                try:
                    name = product.find_element(By.CLASS_NAME, "product-name").text
                    price_text = product.find_element(By.CLASS_NAME, "product-price").text
                    price = float(price_text.replace("₹", "").strip())
                    
                    results.append({
                        "platform": "Zepto",
                        "name": name,
                        "price": price
                    })
                except:
                    continue
            
            return results
        except Exception as e:
            print(f"Error: {e}")
            return []
        finally:
            self.driver.quit()