import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        # Lanciamo il browser (senza interfaccia grafica)
        browser = await p.chromium.launch(headless=True)
        # Usiamo un profilo utente reale per evitare blocchi
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        url = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
        print(f"--- Navigazione verso: {url} ---")
        
        # Andiamo alla pagina
        await page.goto(url, wait_until="networkidle")

        # ASPETTIAMO: Questo è il punto cruciale. 
        # Aspettiamo che appaia almeno un elemento della lista prodotti (li)
        try:
            print("In attesa del caricamento dei prodotti...")
            await page.wait_for_selector('li[aria-label*="online"]', timeout=30000)
            print("✅ Pagina caricata con successo!")
        except Exception as e:
            print(f"❌ Timeout: I prodotti non sono apparsi. Salvo uno screenshot per capire perché.")
            await page.screenshot(path="error.png")
            await browser.close()
            return

        # Estraiamo i prodotti
        prodotti = await page.query_selector_all('li[aria-label*="online"]')
        print(f"🚀 Trovati {len(prodotti)} prodotti!\n")

        for i, p in enumerate(prodotti, 1):
            # Estraiamo i dati dal codice "vivo" della pagina
            testo_completo = await p.inner_text()
            linee = [line.strip() for line in testo_completo.split('\n') if line.strip()]
            
            # IKEA mette il nome solitamente nella prima riga utile
            nome = linee[0] if len(linee) > 0 else "N/A"
            # Cerchiamo il prezzo (che ha il simbolo €)
            prezzo = next((l for l in linee if "€" in l), "N/A")
            
            print(f"{i}. 📦 {nome} | 💰 {prezzo}")

        # Se vuoi vedere l'HTML finale (quello generato dai JS)
        html_finale = await page.content()
        print("\n--- ANTEPRIMA HTML RIGENERATO (Primi 1000 char) ---")
        print(html_finale[:1000])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
