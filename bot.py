import asyncio
import csv
import os
import requests
from playwright.async_api import async_playwright

# --- CONFIGURAZIONE DIRETTA ---
TELEGRAM_TOKEN = "8716709088:AAHGPkPfjHmzIAoTSObLq9Z0vgDqBR3vQuU"
TELEGRAM_CHAT_ID = "308359205"
CSV_FILE = "prodotti_visti.csv"

def carica_id_visti():
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return {row[0] for row in reader if row}

def salva_nuovo_prodotto(link, nome, prezzo_nuovo, img):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([link, nome, prezzo_nuovo, img])

def invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link, img_url):
    info_prezzo = f"💰 *Prezzo:* ~~€{prezzo_vecchio}~~ → *€{prezzo_nuovo}*" if prezzo_vecchio != "N/D" else f"💰 *Prezzo:* *€{prezzo_nuovo}*"
    testo = f"🔹 *Nome:* *{nome}*\n{info_prezzo}\n🔗 [APRI]({link})"
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo, "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url_api, data=payload)
        r.raise_for_status()
    except: pass

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Impostiamo una lingua italiana per evitare che il sito cambi layout
        context = await browser.new_context(locale="it-IT", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        visti = carica_id_visti()
        
        url = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
        print("--- Avvio Scansione Approfondita ---")
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # --- NOVITÀ: SCROLL AUTOMATICO ---
            # Questo assicura che tutti i prodotti "pigri" vengano caricati
            for _ in range(5): 
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(1)

            # Aspetta che gli elementi siano visibili
            await page.wait_for_selector('li[class*="item"]', timeout=30000)
            
            # Prendiamo tutti i contenitori dei prodotti
            elementi = await page.query_selector_all('li:has(a[href*="/napoli/"])')
            print(f"Prodotti rilevati sulla pagina: {len(elementi)}")

            nuovi_trovati = 0
            for el in elementi:
                try:
                    link_elem = await el.query_selector('a')
                    href = await link_elem.get_attribute('href')
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if "http" not in href else href

                    if link_completo in visti:
                        continue

                    # Estrazione più flessibile
                    nome_elem = await el.query_selector('h3, .typography-heading-xs')
                    nome = (await nome_elem.inner_text()).strip() if nome_elem else "Prodotto IKEA"

                    # Prezzi
                    p_nuovo_el = await el.query_selector('.price--medium .price__integer, .price__integer')
                    prezzo_nuovo = await p_nuovo_el.inner_text() if p_nuovo_el else "N/D"

                    p_vecchio_el = await el.query_selector('.price--small .price__integer')
                    prezzo_vecchio = await p_vecchio_el.inner_text() if p_vecchio_el else "N/D"

                    img_elem = await el.query_selector('img')
                    img_url = await img_elem.get_attribute('src') if img_elem else ""

                    salva_nuovo_prodotto(link_completo, nome, prezzo_nuovo, img_url)
                    visti.add(link_completo)
                    nuovi_trovati += 1
                    
                    invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link_completo, img_url)
                    print(f"✅ Inviato: {nome}")
                    await asyncio.sleep(1) # Evita spam block da Telegram

                except Exception as e:
                    print(f"⚠️ Salto un elemento per errore tecnico: {e}")

            if nuovi_trovati == 0:
                print("Nessun nuovo prodotto rilevato.")

        except Exception as e:
            print(f"❌ Errore critico: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
