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
    if not os.path.exists(CSV_FILE): return set()
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        return {row[0] for row in csv.reader(f) if row}

def salva_nuovo_prodotto(link, nome, prezzo, img):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([link, nome, prezzo, img])

def pulisci_prezzo(testo):
    if not testo: return "0"
    return re.sub(r'[^\d,]', '', testo).replace(',', '.')

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        visti = carica_id_visti()
        
        try:
            print("Caricamento IKEA Napoli...")
            await page.goto(URL_IKEA, wait_until="networkidle", timeout=60000)
            
            # Scroll profondo per attivare il caricamento di tutti i <li>
            for _ in range(10):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(1)

            # Selettore basato sulla lista prodotti trovata nell'HTML fornito
            prodotti = await page.query_selector_all('li[aria-label]')
            print(f"📦 Prodotti totali rilevati: {len(prodotti)}")

            nuovi_contatore = 0
            for el in prodotti:
                try:
                    # Estrazione Link (gestisce sia <a> che ID generici)
                    link_el = await el.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    # Se non c'è link diretto, usiamo l'ID della lista come riferimento unico
                    prod_id = href if href else await el.evaluate("el => el.getAttribute('aria-label') + el.innerText.slice(0,20)")
                    
                    if prod_id in visti: continue

                    # Nome Prodotto
                    nome_el = await el.query_selector('.typography-heading-xs')
                    nome = (await nome_el.inner_text()).strip() if nome_el else "Prodotto IKEA"

                    # Descrizione (per dettagli come 'imballo danneggiato')
                    desc_el = await el.query_selector('.typography-body-m')
                    desc = (await desc_el.inner_text()).strip() if desc_el else ""

                    # Prezzo Nuovo (Intero + Decimale)
                    p_int = await el.query_selector('.price--medium .price__integer')
                    p_dec = await el.query_selector('.price--medium .price__decimal')
                    val_nuovo = await p_int.inner_text() if p_int else "0"
                    if p_dec: val_nuovo += await p_dec.inner_text()

                    # Prezzo Vecchio
                    p_old = await el.query_selector('.price--comparison .price__integer')
                    val_vecchio = await p_old.inner_text() if p_old else "N/D"

                    # Immagine
                    img_el = await el.query_selector('img.image')
                    img_url = await img_el.get_attribute('src') if img_el else ""

                    # Invio Telegram
                    testo_tg = f"🌟 *NUOVO ARRIVO IKEA NAPOLI*\n\n🔹 *{escape_markdown(nome)}*\n"
                    if desc: testo_tg += f"📝 _{escape_markdown(desc)}_\n"
                    
                    if val_vecchio != "N/D":
                        testo_tg += f"💰 *Prezzo:* ~{val_vecchio}€~ → *{val_nuovo}€*\n"
                    else:
                        testo_tg += f"💰 *Prezzo:* *{val_nuovo}€*\n"
                    
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if href and "#" in href else URL_IKEA
                    testo_tg += f"\n🔗 [Apri]({link_completo})"

                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", 
                                 data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo_tg, "parse_mode": "MarkdownV2"})
                    
                    salva_nuovo_prodotto(prod_id, nome, val_nuovo, img_url)
                    visti.add(prod_id)
                    nuovi_contatore += 1
                    print(f"✨ Inviato: {nome}")
                    await asyncio.sleep(0.5)

                except Exception as e:
                    continue

            print(f"------------------------------------------\n🚀 Fine. Nuovi: {nuovi_contatore}")

        except Exception as e: print(f"❌ Errore: {e}")
        finally: await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
