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
    """Protegge i caratteri speciali per il formato MarkdownV2 di Telegram."""
    if not text: return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def carica_id_visti():
    """Carica lo storico dei prodotti per evitare duplicati."""
    if not os.path.exists(CSV_FILE): return set()
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        return {row[0] for row in csv.reader(f) if row}

def salva_nuovo_prodotto(link, nome, prezzo, img):
    """Registra il prodotto nel file CSV."""
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([link, nome, prezzo, img])

def calcola_risparmio(nuovo, vecchio):
    """Calcola la percentuale di sconto tra prezzo vecchio e nuovo."""
    try:
        n_str = re.sub(r'[^\d.,]', '', nuovo).replace(',', '.')
        v_str = re.sub(r'[^\d.,]', '', vecchio).replace(',', '.')
        n = float(n_str)
        v = float(v_str)
        if v <= n: return 0
        return round(((v - n) / v) * 100)
    except:
        return 0

def invia_telegram(nome, desc, prezzo_nuovo, prezzo_vecchio, link, img_url):
    """Formatta e invia la notifica a Telegram."""
    nome_esc = escape_markdown(nome)
    desc_esc = escape_markdown(desc)
    p_nuovo_esc = escape_markdown(prezzo_nuovo)
    p_vecchio_esc = escape_markdown(prezzo_vecchio)
    risparmio = calcola_risparmio(prezzo_nuovo, prezzo_vecchio)
    
    info_prezzo = f"💰 *Prezzo:* ~{p_vecchio_esc}€~ → *{p_nuovo_esc}€*\n📉 *Risparmio:* 🔥 *{risparmio}%*" if risparmio > 0 else f"💰 *Prezzo:* *{p_nuovo_esc}€*"
    
    testo = f"🌟 *NUOVO ARRIVO IKEA NAPOLI*\n\n🔹 *{nome_esc}*\n"
    if desc: testo += f"📝 _{desc_esc}_\n"
    testo += f"{info_prezzo}\n\n🔗 [Vedi Dettagli]({link})"
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": testo, "parse_mode": "MarkdownV2"}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Errore invio Telegram: {e}")

async def run_bot():
    async with async_playwright() as p:
        # Lancio browser con User Agent realistico
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="it-IT"
        )
        page = await context.new_page()
        visti = carica_id_visti()
        
        try:
            print("🚀 Avvio navigazione...")
            # Usiamo 'commit' invece di 'networkidle' per evitare timeout dovuti a tracker lenti
            await page.goto(URL_IKEA, wait_until="commit", timeout=60000)
            
            print("⏳ Attesa caricamento dinamico (10s)...")
            await asyncio.sleep(10)
            
            print("🖱️ Scorrimento pagina per caricare tutti i prodotti...")
            for i in range(8):
                await page.mouse.wheel(0, 1200)
                await asyncio.sleep(1.5)
            
            # Selettore basato sull'analisi del tuo file HTML (li con aria-label)
            selector_prod = 'li[aria-label]'
            await page.wait_for_selector(selector_prod, timeout=20000)
            elementi = await page.query_selector_all(selector_prod)

            print(f"\n✅ SCANSIONE COMPLETATA")
            print(f"📦 Prodotti rilevati sulla pagina: {len(elementi)}")
            print(f"------------------------------------------")

            nuovi_contatore = 0
            for el in elementi:
                try:
                    # Estrazione Link
                    link_el = await el.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    
                    # Generiamo un ID unico basato sull'href o sull'aria-label se l'href manca
                    prod_id = href if (href and href != "#") else await el.get_attribute('aria-label')
                    
                    if not prod_id or prod_id in visti:
                        continue

                    # Nome e Descrizione
                    nome_el = await el.query_selector('.typography-heading-xs')
                    nome = (await nome_el.inner_text()).strip() if nome_el else "Prodotto IKEA"
                    
                    desc_el = await el.query_selector('.typography-body-m')
                    desc = (await desc_el.inner_text()).strip() if desc_el else ""

                    # Prezzo Nuovo (Integer + Decimal)
                    p_int = await el.query_selector('.price__integer')
                    p_dec = await el.query_selector('.price__decimal')
                    val_nuovo = await p_int.inner_text() if p_int else "0"
                    if p_dec:
                        dec_txt = await p_dec.inner_text()
                        val_nuovo += dec_txt if ',' in dec_txt else f",{dec_txt}"

                    # Prezzo Vecchio
                    p_old = await el.query_selector('.price--comparison .price__integer, .price--small .price__integer')
                    val_vecchio = await p_old.inner_text() if p_old else "N/D"

                    # Immagine (gestione lazy loading)
                    img_el = await el.query_selector('img')
                    img_url = await img_el.get_attribute('src') if img_el else ""
                    if img_url and img_url.startswith('data:image'): # Se è un placeholder, cerca data-src
                         img_url = await img_el.get_attribute('data-src') or img_url

                    # Costruzione link finale
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{href}" if (href and "#" in href) else URL_IKEA

                    # Invio e Salvataggio
                    invia_telegram(nome, desc, val_nuovo, val_vecchio, link_completo, img_url)
                    salva_nuovo_prodotto(prod_id, nome, val_nuovo, img_url)
                    visti.add(prod_id)
                    
                    nuovi_contatore += 1
                    print(f"✨ [NUOVO] {nome} - {val_nuovo}€")
                    await asyncio.sleep(1) # Delay anti-spam Telegram

                except Exception as e:
                    continue

            print(f"------------------------------------------")
            print(f"🚀 Fine. Nuovi prodotti inviati: {nuovi_contatore}\n")

        except Exception as e:
            print(f"❌ Errore generale durante l'esecuzione: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
