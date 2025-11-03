# Bestand: discounter_bot.py (voor Render/Docker)

import time
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import logging
import sys
import os

# --- CONFIGURATIE ---
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
MAX_PRICE = 1200.00
found_deals = set()

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

def send_discord_notification(message):
    if not WEBHOOK_URL:
        logging.error("Fout: WEBHOOK_URL is niet ingesteld in Render!")
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        logging.info("Notificatie succesvol verzonden.")
    except Exception as e:
        logging.error(f"Fout bij verzenden naar Discord: {e}")

def scrape_vakantiediscounter():
    site_name = "VakantieDiscounter"
    logging.info(f"[{site_name}] Start check op Render...")
    driver = None
    try:
        logging.info("Browser wordt opgestart in headless modus...")
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        driver = uc.Chrome(options=options)
        logging.info("Browser succesvol opgestart.")
        
        url = "https://www.vakantiediscounter.nl/zoekresultaten?arrivaldateend=2026-04-30&countrycode=AN&departuredatestart=2026-02-01&region=curacao&room=2_0_0&transporttype=VL&trip_duration=9"
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # Reeks pop-up handelingen...
        try: wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Alles toestaan')]"))).click(); logging.info("Cookie banner weggeklikt.")
        except: logging.warning("Cookie banner niet gevonden.")
        
        # Geef de pagina even de tijd om de volgende popups te laden
        time.sleep(3)
        
        # De rest van de popups
        try: wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Sluiten']"))).click(); logging.info("'Vakantietegoed' pop-up gesloten.")
        except: logging.warning("'Vakantietegoed' pop-up niet gevonden.")
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(., 'Nee')]"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Volgende')]"))).click()
            logging.info("'Kaart gebruikt' pop-up verwerkt.")
        except: logging.warning("'Kaart gebruikt' pop-up niet gevonden.")
        try: wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Sluiten']"))).click(); logging.info("'Bedankt voor feedback' melding gesloten.")
        except: logging.warning("'Bedankt voor feedback' melding niet gevonden.")

        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component='acco-card']")))
        logging.info("Deal-kaarten gevonden! Pagina wordt geparsed.")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        results = soup.find_all('div', {'data-component': 'acco-card'})
        
        logging.info(f"SUCCESS: {len(results)} deals gevonden op de pagina.")
        # ... De rest van de code blijft hetzelfde ...

    except Exception as e:
        logging.critical(f"FATALE FOUT: {e}", exc_info=True)
        if driver:
             driver.save_screenshot("render_failure.png")
             logging.info("Screenshot gemaakt van de fout (niet downloadbaar).")
    finally:
        if driver:
            driver.quit()
            logging.info("Browser sessie afgesloten.")

if __name__ == "__main__":
    print("--- Definitieve Curaçao Deal Bot (Render) ---", flush=True)
    scrape_vakantiediscounter()
    print("--- Script succesvol voltooid. ---", flush=True)
