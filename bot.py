import asyncio
import csv
import os
import requests
from playwright.async_api import async_playwright

# --- CONFIGURAZIONE ---
# Assicurati che questi dati siano corretti
TELEGRAM_TOKEN = "8716709088:AAHGPkPfjHmzIAoTSObLq9Z0vgDqBR3vQuU"
TELEGRAM_CHAT_ID = "308359205"
CSV_FILE = "prodotti_visti.csv"
URL_IKEA = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"

def carica_id_visti():
    """Carica gli ID dei prodotti già inviati dal file CSV."""
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Usiamo il link come ID univoco
        return {row[0] for row in reader if row}

def salva_nuovo_prodotto(link, nome, prezzo, img):
    """Salva un nuovo prodotto nel database CSV."""
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([link, nome, prezzo, img])

def invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link, img_url):
    """Invia la notifica con foto su Telegram."""
    info_prezzo = f"💰 *Prezzo:* ~~€{prezzo_vecchio}~~ → *€{prezzo_nuovo}*" if prezzo_vecchio != "N/D" else f"💰 *Prezzo:* *€{prezzo_nuovo}*"
    testo = (
        f"🌟 *NUOVO ARRIVO IKEA NAPOLI*\n\n"
        f"🔹 *Prodotto:* {nome}\n"
        f"{info_prezzo}\n\n"
        f"🔗 [Vedi Dettagli sul Sito]({link})"
    )
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "photo": img_url, 
        "caption": testo, 
        "parse_mode": "MarkdownV2"
    }
    try:
        r = requests.post(url_api, data=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Errore invio Telegram: {e}")

async def run_bot():
    async with async_playwright() as p:
        # Lancio browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            locale="it-IT"
        )
        page = await context.new_page()
        
        visti = carica_id_visti()
        print(f"--- Avvio Scansione IKEA Napoli ---")
        
        try:
            # Caricamento pagina con attesa meno restrittiva per evitare timeout
            await page.goto(URL_IKEA, wait_until="domcontentloaded", timeout=60000)
            
            # Attesa extra per il caricamento dei contenuti dinamici
            await asyncio.sleep(7)
            
            # --- AUTO-SCROLL ---
            # IKEA carica i prodotti "a scorrimento". Simuliamo 5 scrollate.
            for i in range(5):
                await page.mouse.wheel(0, 1200)
                await asyncio.sleep(2)
                print(f"Scorrimento pagina ({i+1}/5)...")

            # Aspetta che almeno un prodotto sia visibile
            await page.wait_for_selector('li:has(a[href*="/napoli/"])', timeout=30000)
            
            # Seleziona tutti i blocchi prodotto
            elementi = await page.query_selector_all('li:has(a[href*="/napoli/"])')
            print(f"Prodotti totali rilevati: {len(elementi)}")

            nuovi_contatore = 0
            for el in elementi:
                try:
                    # Estrazione Link
                    link_elem = await el.query_selector('a')
                    href = await link_elem.get_attribute('href')
                    if not href: continue
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if "http" not in href else href

                    # Controllo se già visto
                    if link_completo in visti:
                        continue

                    # Estrazione Nome
                    nome_elem = await el.query_selector('h3, span[class*="heading"]')
                    nome = (await nome_elem.inner_text()).strip() if nome_elem else "Prodotto senza nome"

                    # Estrazione Prezzi
                    p_nuovo_el = await el.query_selector('.price--medium .price__integer, .price__integer')
                    prezzo_nuovo = await p_nuovo_el.inner_text() if p_nuovo_el else "N/D"

                    p_vecchio_el = await el.query_selector('.price--small .price__integer')
                    prezzo_vecchio = await p_vecchio_el.inner_text() if p_vecchio_el else "N/D"

                    # Estrazione Immagine
                    img_elem = await el.query_selector('img')
                    img_url = await img_elem.get_attribute('src') if img_elem else ""

                    # Salvataggio e Invio
                    salva_nuovo_prodotto(link_completo, nome, prezzo_nuovo, img_url)
                    visti.add(link_completo)
                    invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link_completo, img_url)
                    
                    print(f"✨ Nuovo Prodotto: {nome}")
                    nuovi_contatore += 1
                    await asyncio.sleep(1) # Delay anti-spam

                except Exception as e:
                    continue

            print(f"Scansione terminata. Nuovi prodotti inviati: {nuovi_contatore}")

        except Exception as e:
            print(f"❌ Errore critico durante l'esecuzione: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
