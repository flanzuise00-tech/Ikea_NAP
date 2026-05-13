import requests

# URL della pagina (usiamo quello base senza il frammento # che Python non legge)
URL = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
}

def scarica_tutto_html():
    try:
        print(f"--- Richiesta a: {URL} ---")
        response = requests.get(URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        html_content = response.text
        
        # 1. Salviamo l'HTML su un file (utile se lavori in locale o vuoi scaricare l'artefatto)
        with open("pagina_ikea.html", "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # 2. Stampiamo l'HTML nei log di GitHub
        print("\n--- INIZIO HTML COMPLETO ---\n")
        print(html_content)
        print("\n--- FINE HTML COMPLETO ---\n")
        
        print(f"Dimensioni file: {len(html_content)} caratteri.")

    except Exception as e:
        print(f"❌ Errore durante lo scaricamento: {e}")

if __name__ == "__main__":
    scarica_tutto_html()
