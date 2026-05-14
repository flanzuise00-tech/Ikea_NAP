import asyncio
import csv
import os
import requests
import re
import io
import hashlib
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw

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
    storico = {}
    if not os.path.exists(CSV_FILE): return storico
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                try:
                    # Usiamo la colonna 0 come ID (che ora sarà il nostro hash)
                    storico[row[0]] = float(row[2].replace(',', '.'))
                except: continue
    return storico

def salva_prodotto(prod_id, nome, prezzo_str, img_url):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([prod_id, nome, prezzo_str, img_url])

def crea_badge_sconto(url_img, sconto_percentuale):
    try:
        resp = requests.get(url_img, timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        w, h = img.size
        size = int(w * 0.25)
        draw.ellipse([10, 10, size, size], fill=(224, 15, 25, 240))
        testo = f"-{sconto_percentuale}%"
        draw.text((size//4, size//2.5), testo, fill="white")
        out = Image.alpha_composite(img, overlay).convert("RGB")
        img_byte_arr = io.BytesIO()
        out.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()
    except: return None

def invia_telegram(nome, p_nuovo, p_vecchio, link, img_url, ribasso=False):
    try:
        val_n = float(p_nuovo.replace(',', '.'))
        val_v = float(p_vecchio.replace(',', '.')) if (p_vecchio != "N/D") else 0
    except: val_n, val_v = 0, 0

    sconto = round(((val_v - val_n) / val_v) * 100) if val_v > val_n else 0
    titolo = f"📉 *RIBASSO:* {escape_markdown(nome)}" if ribasso else f"🔹 *{escape_markdown(nome)}*"
    
    if val_v > val_n:
        info_prezzo = f"💰 Prezzo: ~{escape_markdown(p_vecchio)}€~ → *{escape_markdown(p_nuovo)}€*\n🔥 *Risparmio:* {sconto}%"
    else:
        info_prezzo = f"💰 Prezzo: *{escape_markdown(p_nuovo)}€*"

    testo = f"{titolo}\n\n{info_prezzo}\n\n🔗 [Apri offerta]({link})"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    foto_con_badge = crea_badge_sconto(img_url, sconto) if sconto > 0 else None

    try:
        if foto_con_badge:
            files = {'photo': ('badge.jpg', foto_con_badge, 'image/jpeg')}
            requests.post(url_api, data={"chat_id": TELEGRAM_CHAT_ID, "caption": testo, "parse_mode": "MarkdownV2"}, files=files, timeout=15)
        else:
            requests.post(url_api, data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo, "parse_mode": "MarkdownV2"}, timeout=15)
    except: pass

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", locale="it-IT")
        page = await context.new_page()
        storico = carica_storico()
        
        try:
            await page.goto(URL_IKEA, wait_until="commit", timeout=60000)
            await asyncio.sleep(10)
            for _ in range(8): await page.mouse.wheel(0, 1000); await asyncio.sleep(1.5)

            prodotti = await page.query_selector_all('li[aria-label]')
            for el in prodotti:
                try:
                    # 1. Nome
                    nome_el = await el.query_selector('.typography-heading-xs')
                    nome = (await nome_el.inner_text()).strip() if nome_el else "Prodotto"

                    # 2. Immagine
                    img_el = await el.query_selector('img')
                    img_url = await img_el.get_attribute('src') if img_el else ""
                    if img_url and img_url.startswith('data:'):
                        img_url = await img_el.get_attribute('data-src') or img_url

                    # 3. Prezzo attuale
                    p_int = await el.query_selector('.price__integer')
                    p_dec = await el.query_selector('.price__decimal')
                    val_nuovo_str = (await p_int.inner_text()).strip() if p_int else "0"
                    if p_dec: val_nuovo_str += "," + (await p_dec.inner_text()).replace(",", "").strip()
                    val_nuovo_float = float(val_nuovo_str.replace(',', '.'))

                    # 4. Link (se manca, puntiamo alla pagina generale di Napoli)
                    link_el = await el.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if (href and "#" in href) else URL_IKEA

                    # --- CREAZIONE ID UNICO (HASH) ---
                    # Anche se il link manca, l'immagine + il nome + il prezzo creano una firma unica
                    identificativo_stringa = f"{nome}_{val_nuovo_str}_{img_url}"
                    prod_id = hashlib.md5(identificativo_stringa.encode()).hexdigest()

                    # 5. Prezzo Vecchio / Sconto
                    val_vecchio_str = "N/D"
                    p_old_el = await el.query_selector('.price--comparison .price__integer, .price--small .price__integer')
                    if p_old_el:
                        val_vecchio_str = re.sub(r'[^\d,]', '', await p_old_el.inner_text()).strip()
                    else:
                        badge_sconto = await el.query_selector('.commercial-message')
                        if badge_sconto:
                            percent_text = await badge_sconto.inner_text()
                            match = re.search(r'(\d+)', percent_text)
                            if match:
                                p_sconto = int(match.group(1))
                                p_originale = val_nuovo_float / (1 - (p_sconto / 100))
                                val_vecchio_str = f"{p_originale:.2f}".replace('.', ',')

                    # --- LOGICA INVIO ---
                    if prod_id not in storico:
                        invia_telegram(nome, val_nuovo_str, val_vecchio_str, link_completo, img_url, ribasso=False)
                        salva_prodotto(prod_id, nome, val_nuovo_str, img_url)
                        storico[prod_id] = val_nuovo_float
                    elif val_nuovo_float < storico[prod_id]:
                        invia_telegram(nome, val_nuovo_str, val_vecchio_str, link_completo, img_url, ribasso=True)
                        salva_prodotto(prod_id, nome, val_nuovo_str, img_url)
                        storico[prod_id] = val_nuovo_float
                        
                    await asyncio.sleep(0.5)
                except Exception: continue
        finally: await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
