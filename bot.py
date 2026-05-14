import asyncio
import csv
import os
import requests
import re
from playwright.async_api import async_playwright

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = "8716709088:AAHGPkPfjHmzIAoTSObLq9Z0vgDqBR3vQuU"
TELEGRAM_CHAT_ID = "308359205"
CSV_FILE = "prodotti_visti.csv"
URL_IKEA = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"

def escape_markdown(text):
    if not text: return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def carica_id_visti():
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return {row[0] for row in reader if row}

def salva_nuovo_prodotto(link, nome, prezzo, img):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([link, nome, prezzo, img])

def calcola_risparmio(nuovo, vecchio):
    try:
        # Pulizia stringhe (rimuove € e converte virgola in punto)
        n = float(nuovo.replace('€', '').replace(',', '.').strip())
        v = float(vecchio.replace('€', '').replace(',', '.').strip())
        if v <= 0: return 0
        percentuale = ((v - n) / v) * 100
        return round(percentuale)
    except:
        return 0

def invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link, img_url):
    nome_esc = escape_markdown(nome)
    p_nuovo_esc = escape_markdown(prezzo_nuovo)
    p_vecchio_esc = escape_markdown(prezzo_vecchio)
    
    risparmio = calcola_risparmio(prezzo_nuovo, prezzo_vecchio)
    
    if prezzo_vecchio != "N/D" and risparmio > 0:
        info_prezzo = (
            f"💰 *Prezzo:* ~{p_vecchio_esc}€~ → *{p_nuovo_esc}€*\n"
            f"📉 *Risparmio:* 🔥 *{risparmio}%*"
        )
    else:
        info_prezzo = f"💰 *Prezzo:* *{p_nuovo_esc}€*"

    testo = (
        f"🔹 *Prodotto:* {nome_esc}\n"
        f"{info_prezzo}\n\n"
        f"🔗 [Apri]({link})"
    )
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo, "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url_api, data=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Errore Telegram: {r.text}")

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...", locale="it-IT")
        page = await context.new_page()
        visti = carica_id_visti()
        
        try:
            await page.goto(URL_IKEA, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(7)
            
            # Scroll per caricare i prodotti
            for _ in range(3):
                await page.mouse.wheel(0, 1500)
                await asyncio.sleep(2)

            await page.wait_for_selector('li:has(a[href*="/napoli/"])', timeout=30000)
            elementi = await page.query_selector_all('li:has(a[href*="/napoli/"])')

            for el in elementi:
                # --- STAMPA HTML NEL TERMINALE ---
                html_prodotto = await el.outer_html()
                print("\n--- DEBUG HTML PRODOTTO ---")
                print(html_prodotto)
                print("---------------------------\n")

                try:
                    link_elem = await el.query_selector('a')
                    href = await link_elem.get_attribute('href')
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if "http" not in href else href

                    if link_completo in visti: continue

                    nome_elem = await el.query_selector('h3, span[class*="heading"]')
                    nome = (await nome_elem.inner_text()).strip() if nome_elem else "Prodotto"

                    # Estrazione prezzi (con gestione selettori IKEA)
                    p_nuovo_el = await el.query_selector('.price--medium .price__integer, .price__integer')
                    prezzo_nuovo = await p_nuovo_el.inner_text() if p_nuovo_el else "0"

                    p_vecchio_el = await el.query_selector('.price--small .price__integer')
                    prezzo_vecchio = await p_vecchio_el.inner_text() if p_vecchio_el else "N/D"

                    img_elem = await el.query_selector('img')
                    img_url = await img_elem.get_attribute('src') if img_elem else ""

                    salva_nuovo_prodotto(link_completo, nome, prezzo_nuovo, img_url)
                    visti.add(link_completo)
                    invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link_completo, img_url)
                    await asyncio.sleep(1) 

                except Exception: continue

        except Exception as e:
            print(f"❌ Errore: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
