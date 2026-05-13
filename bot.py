import requests
from bs4 import BeautifulSoup

# 1. Inserisci qui il link della pagina che vuoi testare
URL = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"

def test_estrazione():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
    }
    
    print(f"--- Inizio scaricamento pagina: {URL} ---")
    
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status() # Controlla se ci sono errori di connessione
        
        # Stampa i primi 500 caratteri dell'HTML per vedere se è leggibile
        print("\n--- ANTEPRIMA HTML (Primi 500 caratteri) ---")
        print(response.text[:500])
        print("-------------------------------------------\n")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Cerchiamo i contenitori dei prodotti
        # Nota: IKEA cambia spesso le classi, queste sono le più comuni per il Second Hand
        prodotti = soup.find_all('div', class_='pip-product-compact')

        print(f"Risultato: Ho trovato {len(prodotti)} prodotti.\n")

        for i, p in enumerate(prodotti, 1):
            # Proviamo a estrarre Titolo e Prezzo
            try:
                nome = p.find('span', class_='pip-header-section__title--small').get_text(strip=True)
                prezzo = p.find('span', class_='pip-price__integer').get_text(strip=True)
                print(f"{i}. PRODOTTO: {nome} | PREZZO: €{prezzo}")
            except AttributeError:
                print(f"{i}. Errore: Alcuni dati mancano per questo elemento.")

    except Exception as e:
        print(f"Errore durante il test: {e}")

if __name__ == "__main__":
    test_estrazione()
