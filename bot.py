import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Aggiungiamo una dimensione finestra standard per far apparire i prodotti correttamente
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        url = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
        print(f"--- Navigazione verso: {url} ---")
        
        try:
            # CAMBIO 1: Usiamo 'domcontentloaded' invece di 'networkidle' (molto più veloce)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # CAMBIO 2: Aspettiamo specificamente che il contenitore dei prodotti appaia
            print("Pagina base caricata. Attendo che i Javascript generino la lista mobili...")
            
            # Aspettiamo il selettore dei prodotti (basato sull'HTML che mi hai dato)
            # Cerchiamo il tag <li> che contiene il link con 'napoli'
            await page.wait_for_selector('li a[href*="/napoli/"]', timeout=45000)
            
            print("✅ Mobili apparsi a schermo!")
            
            # Estraiamo i prodotti
            prodotti = await page.query_selector_all('li:has(a[href*="/napoli/"])')
            print(f"🚀 Trovati {len(prodotti)} prodotti!\n")

            for i, p in enumerate(prodotti[:10], 1):
                testo = await p.inner_text()
                # Pulizia veloce del testo per il terminale
                dati = [line.strip() for line in testo.split('\n') if line.strip()]
                print(f"{i}. " + " | ".join(dati[:3])) # Stampa le prime 3 info (Nome, Prezzo, Stato)

        except Exception as e:
            print(f"❌ Errore durante l'attesa: {e}")
            # Salviamo lo screenshot per vedere cosa è andato storto
            await page.screenshot(path="debug_timeout.png")
            # Stampiamo un pezzo di HTML per capire se siamo in una pagina di errore
            content = await page.content()
            print("\n--- HTML di Debug (Primi 500 char) ---")
            print(content[:500])
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
