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
        n_str = re.sub(r'[^\d.,]', '', nuovo).replace(',', '.')
        v_str = re.sub(r'[^\d.,]', '', vecchio).replace(',', '.')
        n = float(n_str)
        v = float(v_str)
        if v <= n: return 0
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
    except Exception:
        print(f"⚠️ Errore Telegram per {nome}: {r.text}")

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="it-IT"
        )
        page = await context.new_page()
        visti = carica_id_visti()
        
        try:
            print(f"Navigazione su IKEA Napoli...")
            await page.goto(URL_IKEA, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8)
            
            for i in range(3):
                await page.mouse.wheel(0, 2000)
                await asyncio.sleep(2)

            selector = 'li:has(a[href*="/napoli/"])'
            await page.wait_for_selector(selector, timeout=30000)
            elementi = await page.query_selector_all(selector)

            print(f"\n✅ SCANSIONE COMPLETATA")
            print(f"📦 Prodotti totali trovati sulla pagina: {len(elementi)}")
            print(f"------------------------------------------")

            nuovi_contatore = 0
            for el in elementi:
                try:
                    link_elem = await el.query_selector('a')
                    href = await link_elem.get_attribute('href')
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if "http" not in href else href

                    if link_completo in visti: continue

                    nome_elem = await el.query_selector('h3, span[class*="heading"]')
                    nome = (await nome_elem.inner_text()).strip() if nome_elem else "Prodotto IKEA"

                    p_nuovo_el = await el.query_selector('.price--medium .price__integer, .price__integer')
                    prezzo_nuovo = await p_nuovo_el.inner_text() if p_nuovo_el else "0"

                    p_vecchio_el = await el.query_selector('.price--small .price__integer')
                    prezzo_vecchio = await p_vecchio_el.inner_text() if p_vecchio_el else "N/D"

                    img_elem = await el.query_selector('img')
                    img_url = await img_elem.get_attribute('src') if img_elem else ""

                    salva_nuovo_prodotto(link_completo, nome, prezzo_nuovo, img_url)
                    visti.add(link_completo)
                    invia_telegram(nome, prezzo_nuovo, prezzo_vecchio, link_completo, img_url)
                    
                    nuovi_contatore += 1
                    print(f"✨ [NUOVO] {nome} - {prezzo_nuovo}€")
                    await asyncio.sleep(1) 

                except Exception:
                    continue

            print(f"------------------------------------------")
            print(f"🚀 Fine. Nuovi prodotti inviati: {nuovi_contatore}\n")

        except Exception as e:
            print(f"❌ Errore generale: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
