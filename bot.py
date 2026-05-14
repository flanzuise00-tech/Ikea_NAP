import asyncio
import csv
import os
import requests
import re
import io
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = "8716709088:AAHGPkPfjHmzIAoTSObLq9Z0vgDqBR3vQuU"
TELEGRAM_CHAT_ID = "308359205"
CSV_FILE = "prodotti_visti.csv"
URL_IKEA = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"

def escape_markdown(text):
    if not text: return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def carica_storico():
    """Carica lo storico: {id_prodotto: prezzo_float}"""
    storico = {}
    if not os.path.exists(CSV_FILE): return storico
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                try:
                    # row[0] è l'ID/Link, row[2] è il prezzo salvato
                    storico[row[0]] = float(row[2].replace(',', '.'))
                except: continue
    return storico

def salva_prodotto(prod_id, nome, prezzo_str, img_url):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([prod_id, nome, prezzo_str, img_url])

def crea_badge_sconto(url_img, sconto_percentuale):
    """Scarica l'immagine, aggiunge un bollino rosso con lo sconto e ritorna i bytes."""
    try:
        resp = requests.get(url_img, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        
        # Crea overlay per il badge
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Dimensioni dinamiche del bollino (1/4 della larghezza immagine)
        w, h = img.size
        size = int(w * 0.25)
        
        # Disegna cerchio rosso nell'angolo in alto a sinistra
        draw.ellipse([10, 10, size, size], fill=(224, 15, 25, 240))
        
        # Testo dello sconto (usa font di sistema base se non trova altri)
        testo = f"-{sconto_percentuale}%"
        # In assenza di font specifici su GitHub Actions, usiamo una dimensione stimata
        draw.text((size//4, size//2.5), testo, fill="white")
        
        out = Image.alpha_composite(img, overlay).convert("RGB")
        img_byte_arr = io.BytesIO()
        out.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"⚠️ Impossibile creare badge: {e}")
        return None

def invia_telegram(nome, desc, p_nuovo, p_vecchio, link, img_url, ribasso=False):
    # Calcolo logico per lo sconto
    val_n = float(p_nuovo.replace(',', '.'))
    val_v = float(p_vecchio.replace(',', '.')) if p_vecchio != "N/D" else 0
    sconto = round(((val_v - val_n) / val_v) * 100) if val_v > val_n else 0

    # Titolo della notifica
    titolo = "📉 *RIBASSO PREZZO\!*" if ribasso else "🌟 *NUOVO ARRIVO IKEA NAPOLI*"
    
    info_prezzo = f"💰 *Prezzo:* ~{escape_markdown(p_vecchio)}€~ → *{escape_markdown(p_nuovo)}€*"
    if sconto > 0: info_prezzo += f"\n🔥 *Sconto complessivo:* {sconto}%"

    testo = f"{titolo}\n\n🔹 *{escape_markdown(nome)}*\n"
    if desc: testo += f"📝 _{escape_markdown(desc)}_\n"
    testo += f"{info_prezzo}\n\n🔗 [Apri offerta]({link})"

    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    # Se c'è uno sconto, prova a inviare l'immagine col badge
    foto_con_badge = crea_badge_sconto(img_url, sconto) if sconto > 0 else None

    try:
        if foto_con_badge:
            files = {'photo': ('badge.jpg', foto_con_badge, 'image/jpeg')}
            requests.post(url_api, data={"chat_id": TELEGRAM_CHAT_ID, "caption": testo, "parse_mode": "MarkdownV2"}, files=files)
        else:
            requests.post(url_api, data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo, "parse_mode": "MarkdownV2"})
    except:
        print(f"❌ Errore invio Telegram")

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...", locale="it-IT")
        page = await context.new_page()
        
        storico = carica_storico()
        
        try:
            print("Avvio navigazione...")
            await page.goto(URL_IKEA, wait_until="commit", timeout=60000)
            await asyncio.sleep(10)
            
            # Scroll per caricare i prodotti (IKEA Lazy Load)
            for _ in range(8):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(1.5)

            prodotti = await page.query_selector_all('li[aria-label]')
            print(f"Prodotti trovati: {len(prodotti)}")

            for el in prodotti:
                try:
                    # Estrazione dati basata sul tuo esempio HTML
                    link_el = await el.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    # ID unico per il tracking
                    prod_id = href if (href and href != "#") else await el.get_attribute('aria-label')

                    nome_el = await el.query_selector('.typography-heading-xs')
                    nome = (await nome_el.inner_text()).strip() if nome_el else "Prodotto"
                    
                    desc_el = await el.query_selector('.typography-body-m')
                    desc = (await desc_el.inner_text()).strip() if desc_el else ""

                    p_int = await el.query_selector('.price__integer')
                    p_dec = await el.query_selector('.price__decimal')
                    val_nuovo_str = (await p_int.inner_text()).strip() if p_int else "0"
                    if p_dec: val_nuovo_str += "," + (await p_dec.inner_text()).replace(",", "").strip()
                    
                    val_nuovo_float = float(val_nuovo_str.replace(',', '.'))

                    p_old = await el.query_selector('.price--comparison .price__integer, .price--small .price__integer')
                    val_vecchio_str = (await p_old.inner_text()).strip() if p_old else "N/D"

                    img_el = await el.query_selector('img')
                    img_url = await img_el.get_attribute('src') if img_el else ""
                    if img_url and img_url.startswith('data:'):
                        img_url = await img_el.get_attribute('data-src') or img_url

                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if "#" in href else URL_IKEA

                    # --- LOGICA TRACKER ---
                    if prod_id not in storico:
                        print(f"✨ Nuovo: {nome}")
                        invia_telegram(nome, desc, val_nuovo_str, val_vecchio_str, link_completo, img_url, ribasso=False)
                        salva_prodotto(prod_id, nome, val_nuovo_str, img_url)
                        storico[prod_id] = val_nuovo_float
                    elif val_nuovo_float < storico[prod_id]:
                        print(f"📉 Ribasso: {nome} ({storico[prod_id]} -> {val_nuovo_float})")
                        invia_telegram(nome, desc, val_nuovo_str, val_vecchio_str, link_completo, img_url, ribasso=True)
                        salva_prodotto(prod_id, nome, val_nuovo_str, img_url)
                        storico[prod_id] = val_nuovo_float
                        
                    await asyncio.sleep(0.5)

                except Exception as e: continue

        except Exception as e: print(f"Errore: {e}")
        finally: await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
