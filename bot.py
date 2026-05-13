import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        url = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
        print(f"--- Navigazione verso: {url} ---")
        
        try:
            # Caricamento rapido
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Aspettiamo che appaiano i link dei prodotti
            print("In attesa dei prodotti...")
            await page.wait_for_selector('li a[href*="/napoli/"]', timeout=45000)
            
            # Selezioniamo tutti i blocchi prodotto
            prodotti = await page.query_selector_all('li:has(a[href*="/napoli/"])')
            print(f"🚀 Trovati {len(prodotti)} prodotti!\n")

            for i, p in enumerate(prodotti[:15], 1):
                try:
                    # 1. Estrazione Nome
                    nome_elem = await p.query_selector('.typography-heading-xs')
                    nome = await nome_elem.inner_text() if nome_elem else "Nome non trovato"

                    # 2. Estrazione Prezzo Scontato
                    # Cerchiamo l'elemento price__integer. Se ce ne sono due, il secondo è solitamente quello scontato
                    prezzi_elem = await p.query_selector_all('.price__integer')
                    if len(prezzi_elem) > 1:
                        prezzo = await prezzi_elem[1].inner_text()
                    elif len(prezzi_elem) == 1:
                        prezzo = await prezzi_elem[0].inner_text()
                    else:
                        prezzo = "N/D"

                    # 3. Estrazione Link Immagine
                    img_elem = await p.query_selector('img.image')
                    img_url = await img_elem.get_attribute('src') if img_elem else "No image"

                    # 4. Estrazione Link Prodotto (per completezza)
                    link_elem = await p.query_selector('a')
                    link_href = await link_elem.get_attribute('href') if link_elem else ""
                    link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{link_href}"

                    print(f"📦 PRODOTTO {i}")
                    print(f"🔹 Nome: {nome}")
                    print(f"💰 Prezzo: €{prezzo}")
                    print(f"🖼️ Immagine: {img_url}")
                    print(f"🔗 Link: {link_completo}")
                    print("-" * 40)

                except Exception as e:
                    print(f"⚠️ Errore nell'estrazione del prodotto {i}: {e}")

        except Exception as e:
            print(f"❌ Errore generale: {e}")
            await page.screenshot(path="debug_timeout.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
