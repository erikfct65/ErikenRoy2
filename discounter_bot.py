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

# --- LOGGING CONFIGURATIE ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def send_discord_notification(message):
    if not WEBHOOK_URL:
        logging.error("Fout: WEBHOOK_URL is niet ingesteld in GitHub Secrets!")
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        logging.info("Notificatie succesvol verzonden.")
    except Exception as e:
        logging.error(f"Fout bij verzenden naar Discord: {e}")

def scrape_vakantiediscounter():
    site_name = "VakantieDiscounter"
    logging.info(f"[{site_name}] Start check...")
    driver = None
    try:
        logging.info("Browser (undetected_chromedriver) wordt opgestart in headless modus...")
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-sh-usage')
        driver = uc.Chrome(options=options)
        driver.maximize_window()
        logging.info("Browser succesvol opgestart.")
        
        url = "https://www.vakantiediscounter.nl/zoekresultaten?arrivaldateend=2026-04-30&countrycode=AN&departuredatestart=2026-02-01&region=curacao&room=2_0_0&transporttype=VL&trip_duration=9"
        logging.info(f"Pagina wordt geladen: {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)

        # Reeks van pop-up handelingen
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Alles toestaan')]"))).click()
            logging.info("Cookie banner weggeklikt.")
        except: logging.warning("Cookie banner niet gevonden/geklikt.")
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Sluiten']"))).click()
            logging.info("'Vakantietegoed' pop-up gesloten.")
        except: logging.warning("'Vakantietegoed' pop-up niet gevonden/geklikt.")
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(., 'Nee')]"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Volgende')]"))).click()
            logging.info("'Kaart gebruikt' pop-up verwerkt.")
        except: logging.warning("'Kaart gebruikt' pop-up niet gevonden/verwerkt.")
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Sluiten']"))).click()
            logging.info("'Bedankt voor feedback' melding gesloten.")
        except: logging.warning("'Bedankt voor feedback' melding niet gevonden/geklikt.")
        
        # --- DEBUGGING STAP: ALTIJD EEN SCREENSHOT MAKEN ---
        logging.info("Alle pop-ups verwerkt. Screenshot wordt gemaakt voor analyse...")
        screenshot_filename = "server_view.png"
        driver.save_screenshot(screenshot_filename)
        logging.info(f"Screenshot '{screenshot_filename}' succesvol opgeslagen.")
        
        try:
            logging.info("Wachten tot de deal-kaarten ('AccoCard') aanwezig zijn...")
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component='acco-card']")))
            logging.info("Deal-kaarten zijn nu aanwezig. Pagina wordt geparsed.")
        except TimeoutException:
            logging.error("FATALE FOUT: Deal-kaarten niet gevonden.")
            return # Stop het script hier, we hebben de screenshot al

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        results = soup.find_all('div', {'data-component': 'acco-card'})
        
        logging.info(f"SUCCESS: {len(results)} deals gevonden op de pagina.")
        deals_found_count = 0
        for item in results:
            title_element = item.select_one('h3.AccoCard__title > a[data-component="acco-link"]')
            price_element = item.select_one('span.BasePrice__price.PriceMarker__price')
            
            if title_element and price_element:
                price_text = price_element.text.strip()
                if not price_text: continue
                
                try:
                    price_pp = float(price_text.replace('€', '').replace('.', '').replace(',', '.').strip())
                except (ValueError, TypeError):
                    logging.warning(f"Prijsconversie mislukt voor: '{price_text}'")
                    continue
                
                if price_pp < MAX_PRICE:
                    deals_found_count += 1
                    name = title_element.text.strip()
                    deal_url = "https://www.vakantiediscounter.nl" + title_element.get('href', '')
                    
                    vertrekdatum = 'N/A'
                    reisduur = 'N/A'
                    
                    info_list = item.select_one("ul.AccoCard__info-list")
                    if info_list:
                        date_li = info_list.find("li")
                        if date_li:
                            departure_date_element = date_li.select_one("span.InlineItem__label")
                            if departure_date_element:
                                vertrekdatum = departure_date_element.text.strip()

                            duration_element = date_li.select_one("span.InlineItem__subtext")
                            if duration_element:
                                reisduur = duration_element.text.strip().replace('(', '').replace(')', '')

                    logging.info(f"--> DEAL GEVONDEN: {name} voor €{price_pp:.2f}")
                    
                    totaalprijs = price_pp * 2
                    message = (
                        f"🎉 **DEAL GEVONDEN!** 🎉\n\n"
                        f"**Hotel:** {name}\n"
                        f"**Vertrekdatum:** {vertrekdatum}\n"
                        f"**Reisduur:** {reisduur}\n"
                        f"**Prijs p.p.:** €{price_pp:.2f} (Totaal ca.: €{totaalprijs:.2f})\n\n"
                        f"**Link naar Deal:** {deal_url}\n\n"
                        "@everyone"
                    )
                    
                    send_discord_notification(message)
        
        if deals_found_count == 0:
            logging.info(f"Geen deals onder de €{MAX_PRICE:.2f} gevonden in deze run.")

    except Exception as e:
        logging.critical(f"FATALE FOUT in scrape_vakantiediscounter: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logging.info("Browser sessie afgesloten.")

# --- HOOFDPROGRAMMA ---
if __name__ == "__main__":
    print("--- Definitieve Curaçao Deal Bot (VakantieDiscounter) ---", flush=True)
    scrape_vakantiediscounter()
    print("--- Script succesvol voltooid. ---", flush=True)
