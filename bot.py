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

def pulisci_prezzo(testo):
    if not testo: return "0"
    # Estrae solo i numeri e la virgola
    match = re.search(r'(\d+[\.,]\d+)', testo)
    if match:
        return match.group(1).replace('.', ',')
    # Prova a cercare solo l'intero se non ci sono decimali
    match_int = re.search(r'(\d+)', testo)
    return match_int.group(1) if match_int else "0"

def carica_storico():
    storico = {}
    if not os.path.exists(CSV_FILE): return storico
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                try: storico[row[0]] = float(row[2].replace(',', '.'))
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

def invia_telegram(nome, p_nuovo, p_vecchio, disp, link, img_url, ribasso=False):
    # Logica per gestire range di prezzi (es: "2,97 - 3,20")
    prezzo_visualizzato = p_nuovo
    try:
        val_n = float(p_nuovo.split('-')[0].strip().replace(',', '.'))
        val_v = float(p_vecchio.replace(',', '.')) if p_vecchio != "N/D" else 0
    except: val_n, val_v = 0, 0

    sconto = round(((val_v - val_n) / val_v) * 100) if val_v > val_n else 0
    
    titolo = f"📉 *RIBASSO:* {escape_markdown(nome)}" if ribasso else f"🔹 *{escape_markdown(nome)}*"
    
    # Costruzione Info Prezzo
    if val_v > val_n:
        info_prezzo = f"💰 Prezzo: ~{escape_markdown(p_vecchio)}€~ → *{escape_markdown(p_nuovo)}€*\n🔥 *Risparmio:* {sconto}%"
    else:
        info_prezzo = f"💰 Prezzo: *{escape_markdown(p_nuovo)}€*"

    # Aggiunta disponibilità se presente
    disponibilita = f"\n📦 *Disponibilità:* {escape_markdown(disp)}" if disp else ""

    testo = f"{titolo}\n\n{info_prezzo}{disponibilita}\n\n🔗 [Apri offerta]({link})"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    foto_con_badge = crea_badge_sconto(img_url, sconto) if sconto > 5 else None

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
        context = await browser.new_context(user_agent="Mozilla/5.0...", locale="it-IT")
        page = await context.new_page()
        storico = carica_storico()
        
        try:
            await page.goto(URL_IKEA, wait_until="commit", timeout=60000)
            await asyncio.sleep(10)
            for _ in range(8): await page.mouse.wheel(0, 1000); await asyncio.sleep(1.5)

            prodotti = await page.query_selector_all('li[aria-label]')
            for el in prodotti:
                try:
                    nome_el = await el.query_selector('.typography-heading-xs')
                    nome = (await nome_el.inner_text()).strip() if nome_el else "Prodotto"

                    # --- LOGICA PREZZI CON SR-TEXT ---
                    prezzi_sr = await el.query_selector_all('.price__sr-text')
                    val_nuovo_str = ""
                    val_vecchio_str = "N/D"

                    for psr in prezzi_sr:
                        txt = await psr.inner_text()
                        if "Prezzo precedente" in txt:
                            val_vecchio_str = pulisci_prezzo(txt)
                        else:
                            # Se ci sono più prezzi (caso 2), li uniamo
                            p_pulito = pulisci_prezzo(txt)
                            val_nuovo_str = f"{val_nuovo_str} - {p_pulito}" if val_nuovo_str else p_pulito

                    # --- LOGICA DISPONIBILITÀ ---
                    disp_txt = ""
                    list_items = await el.query_selector_all('.list-view-item__title')
                    for item in list_items:
                        it_txt = await item.inner_text()
                        if "Disponibile" in it_txt:
                            # Estrae "4" da "4 Disponibile presso..."
                            match_disp = re.search(r'(\d+)', it_txt)
                            disp_txt = f"{match_disp.group(1)} pezzi" if match_disp else "Disponibile"

                    # IMMAGINE E LINK
                    img_el = await el.query_selector('img')
                    img_url = await img_el.get_attribute('src') if img_el else ""
                    link_el = await el.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if (href and "#" in href) else URL_IKEA
                    
                    ident_str = f"{nome}_{val_nuovo_str}_{img_url}"
                    prod_id = hashlib.md5(ident_str.encode()).hexdigest()

                    # INVIO
                    if prod_id not in storico:
                        invia_telegram(nome, val_nuovo_str, val_vecchio_str, disp_txt, link_completo, img_url)
                        salva_prodotto(prod_id, nome, val_nuovo_str, img_url)
                        storico[prod_id] = float(val_nuovo_str.split('-')[0].strip().replace(',', '.'))
                except Exception: continue
        finally: await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
