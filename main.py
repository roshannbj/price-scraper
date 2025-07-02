import streamlit as st
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager



import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time


def get_price(url):
    session = requests.Session()
    domain = urlparse(url).netloc
    if 'amazon.' in domain or 'bol.com' in domain:
        # Use Selenium for Amazon and bol.com
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(url)
            time.sleep(2)
            if 'amazon.' in domain:
                price_whole = driver.find_elements(By.CLASS_NAME, 'a-price-whole')
                price_fraction = driver.find_elements(By.CLASS_NAME, 'a-price-fraction')
                if price_whole:
                    price = price_whole[0].text
                    if price_fraction:
                        price += ',' + price_fraction[0].text
                    driver.quit()
                    return price
                print("Price not found on the Amazon page (Selenium).")
                driver.quit()
                return None
            elif 'bol.com' in domain:
                price_whole = driver.find_elements(By.CLASS_NAME, 'promo-price')
                price_fraction = driver.find_elements(By.CLASS_NAME, 'promo-price__fraction')
                if price_whole:
                    # The whole price may include the fraction as a child, so remove the fraction text if present
                    price = price_whole[0].text.strip()
                    fraction = price_fraction[0].text.strip() if price_fraction else ''
                    # Remove the fraction from the whole if present
                    if fraction and fraction in price:
                        price = price.replace(fraction, '')
                    # Remove any newlines or extra spaces
                    price = price.replace('\n', '').replace(' ', '')
                    if fraction:
                        price = f"{price},{fraction}"
                    driver.quit()
                    return price
                print("Price not found on the bol.com page (Selenium).")
                driver.quit()
                return None
        except Exception as e:
            print(f"Selenium error: {e}")
            return None
    else:
        # Use requests/BeautifulSoup for other sites
        if 'easytoys.nl' in domain:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        else:
            headers = {"User-Agent": "Mozilla/5.0"}
        time.sleep(1)
        try:
            response = session.get(url, headers=headers, timeout=10)
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return None
        if response.status_code != 200:
            print(f"Failed to fetch page: {response.status_code}")
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        if 'easytoys.nl' in domain:
            price_tag = soup.find('span', class_='product-price product-price--new product-price--lg')
            if price_tag:
                return price_tag.get_text(strip=True)
            price_spans = soup.find_all('span', class_=lambda x: x and 'product-price' in x)
            if price_spans:
                print("Found the following price-like elements:")
                for tag in price_spans:
                    print(tag, tag.get_text(strip=True))
                return price_spans[0].get_text(strip=True)
            print("Price not found on the page.")
            return None
        else:
            print("Unsupported website.")
            return None


from serpapi import GoogleSearch
import re


# IMPORTANT: Set your SerpApi key in .streamlit/secrets.toml as:
# [serpapi]
# api_key = "YOUR_SERPAPI_KEY"
SERPAPI_KEY = st.secrets["serpapi"]["api_key"]

def get_serp_links(gtin, max_results=50):
    links = []
    for start in range(0, max_results, 10):
        params = {
            "engine": "google",
            "q": gtin,
            "hl": "nl",
            "gl": "nl",
            "api_key": SERPAPI_KEY,
            "start": start
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        organic = results.get("organic_results", [])
        for res in organic:
            link = res.get("link")
            if link and link not in links:
                links.append(link)
        # Stop if there are no more results
        if len(organic) < 10:
            break
        if len(links) >= max_results:
            break
    return links[:max_results]

def parse_price(price):
    if not price:
        return None
    price = re.sub(r'[^0-9,]', '', price)
    price = price.replace(',', '.')
    try:
        return float(price)
    except Exception:
        return None

st.title("GTIN Price Comparison: easytoys.nl vs bol.com")
st.write("Enter a GTIN to compare prices from easytoys.nl and bol.com (SERP powered by SerpApi)")

gtin = st.text_input("Enter GTIN:")

if gtin:
    with st.spinner("Searching Google and scraping prices..."):
        serp_links = get_serp_links(gtin, max_results=50)
        url_easytoys = None
        url_bol = None
        for link in serp_links:
            if not url_easytoys and "easytoys.nl" in link:
                url_easytoys = link
            if not url_bol and "bol.com" in link:
                url_bol = link
            if url_easytoys and url_bol:
                break

        if not url_easytoys and not url_bol:
            st.error("No easytoys.nl or bol.com links found in SERP for this GTIN.")
        else:
            price1 = get_price(url_easytoys) if url_easytoys else None
            price2 = get_price(url_bol) if url_bol else None

            parsed1 = parse_price(price1)
            parsed2 = parse_price(price2)
            diff = None
            table = []
            if url_easytoys:
                table.append(["easytoys.nl", url_easytoys, price1])
            if url_bol:
                table.append(["bol.com", url_bol, price2])
            if parsed1 is not None and parsed2 is not None:
                diff = round(parsed1 - parsed2, 2)
                table.append(["Difference", "", f"{diff}"])
            st.table(table)
