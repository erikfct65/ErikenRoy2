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
    logging.info(f"[{site_name}] Start check met 'onder de radar' strategie...")
    driver = None
    try:
        logging.info("Browser wordt opgestart met menselijke eigenschappen...")
        options = uc.ChromeOptions()
        options.add_argument('--headless=new') # 'new' is de modernere headless-modus
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # --- STRATEGIE AANPASSINGEN ---
        # 1. Forceer een veelvoorkomende User-Agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
        # 2. Stel een standaard, realistische browsergrootte in
        options.add_argument('window-size=1920,1080')
        
        driver = uc.Chrome(options=options)
        logging.info("Browser succesvol opgestart.")
        
        wait = WebDriverWait(driver, 15) # Iets meer geduld

        # --- STRATEGIE AANPASSING: BEZOEK EERST DE HOMEPAGE ---
        homepage_url = "https://www.vakantiediscounter.nl/"
        logging.info(f"Stap 1: Bezoek de homepage om cookies te zetten: {homepage_url}")
        driver.get(homepage_url)
        
        # Wacht op de cookie-banner op de homepage en klik deze weg
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Alles toestaan')]"))).click()
            logging.info("Cookie banner op homepage weggeklikt.")
            time.sleep(2) # Korte pauze
        except:
            logging.warning("Cookie banner niet gevonden op de homepage, of al geaccepteerd.")

        # --- GA NU PAS NAAR DE DEALS PAGINA ---
        deals_url = "https://www.vakantiediscounter.nl/zoekresultaten?arrivaldateend=2026-04-30&countrycode=AN&departuredatestart=2026-02-01&region=curacao&room=2_0_0&transporttype=VL&trip_duration=9"
        logging.info(f"Stap 2: Navigeer nu naar de deals pagina: {deals_url}")
        driver.get(deals_url)
        
        # We hoeven de pop-ups waarschijnlijk niet opnieuw te sluiten, maar voor de zekerheid proberen we het.
        # De 'try...except' blokken vangen dit netjes af als ze niet verschijnen.
        try: wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Sluiten']"))).click(); logging.info("'Vakantietegoed' pop-up gesloten.")
        except: pass
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(., 'Nee')]"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Volgende')]"))).click()
            logging.info("'Kaart gebruikt' pop-up verwerkt.")
        except: pass
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Sluiten']"))).click()
            logging.info("'Bedankt voor feedback' melding gesloten.")
        except: pass

        # --- DEBUGGING SCREENSHOT BLIJFT ACTIEF ---
        logging.info("Screenshot wordt gemaakt voor analyse...")
        driver.save_screenshot("server_view.png")
        logging.info("Screenshot 'server_view.png' opgeslagen.")
        
        try:
            logging.info("Wachten tot de deal-kaarten aanwezig zijn...")
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component='acco-card']")))
            logging.info("Deal-kaarten zijn nu aanwezig.")
        except TimeoutException:
            logging.error("FATALE FOUT: Zelfs met de nieuwe strategie zijn de deal-kaarten niet geladen.")
            return

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        results = soup.find_all('div', {'data-component': 'acco-card'})
        
        logging.info(f"SUCCESS: {len(results)} deals gevonden op de pagina.")
        # ... De rest van de code voor het parsen en versturen blijft exact hetzelfde ...
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
