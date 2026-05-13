import asyncio
import csv
import os
import requests
from playwright.async_api import async_playwright

# --- CONFIGURAZIONE DIRETTA ---
TELEGRAM_TOKEN = "8716709088:AAHGPkPfjHmzIAoTSObLq9Z0vgDqBR3vQuU"
TELEGRAM_CHAT_ID = "308359205"
CSV_FILE = "prodotti_visti.csv"
# ------------------------------

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
    """Invia il messaggio con entrambi i prezzi su Telegram."""
    # Se il prezzo vecchio esiste, lo barriamo (formattazione strike-through)
    info_prezzo = f"💰 *Prezzo:* ~~€{prezzo_vecchio}~~ → *€{prezzo_nuovo}*" if prezzo_vecchio != "N/D" else f"💰 *Prezzo:* *€{prezzo_nuovo}*"
    
    testo = (
        f"🔹 *Nome:* *{nome}*\n"
        f"{info_prezzo}\n"
        f"🔗 [APRI]({link})"
    )
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": img_url, 
        "caption": testo,
        "parse_mode": "MarkdownV2" # Usiamo MarkdownV2 per il barrato (~~)
    }
    
    try:
        r = requests.post(url_api, data=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Errore invio Telegram: {e}")

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        visti = carica_id_visti()
        
        url = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
        print(f"--- Controllo nuovi arrivi IKEA Napoli ---")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('li a[href*="/napoli/"]', timeout=45000)
            
            elementi = await page.query_selector_all('li:has(a[href*="/napoli/"])')
            nuovi_trovati = 0

            for el in elementi:
                link_elem = await el.query_selector('a')
                link_raw = await link_elem.get_attribute('href')
                link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{link_raw}"

                if link_completo in visti:
                    continue

                # 1. Nome
                nome_elem = await el.query_selector('.typography-heading-xs')
                nome = await nome_elem.inner_text() if nome_elem else "N/D"

                # 2. Prezzo Scontato (Nuovo)
                prezzi_scontati = await el.query_selector_all('.price--medium .price__integer')
                prezzo_nuovo = await prezzi_scontati[0].inner_text() if prezzi_scontati else "N/D"

                # 3. Prezzo Precedente (Vecchio)
                # IKEA usa spesso .price--small per il prezzo barrato
                prezzi_vecchi = await el.query_selector_all('.price--small .price__integer')
                prezzo_vecchio = await prezzi_vecchi[0].inner_text() if prezzi_vecchi else "N/D"

                # 4. Immagine
                img_elem = await el.query_selector('img.image')
                img_url = await img_elem.get_attribute('src') if img_elem else ""

                # Salva e Invia
                salva_nuovo_prodotto(link_completo, nome, prezzo_nuovo, img_url)
                visti.add(link_completo)
                nuovi_trovati += 1
                
                # Output log migliorato
                print(f"📦 PRODOTTO {nuovi_trovati}")
                print(f"🔹 Nome: {nome}")
                print(f"💰 Prezzo: €{prezzo_nuovo} (Precedente: €{prezzo_vecchio})")
                print(f"🖼️ Immagine: {img_url}")
                print(f"🔗 Link: {link_completo}")
                print("-" * 40)
                
                # Invio Telegram
                invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link_completo, img_url)

            if nuovi_trovati == 0:
                print("Nessuna novità stasera.")

        except Exception as e:
            print(f"❌ Errore durante l'esecuzione: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
