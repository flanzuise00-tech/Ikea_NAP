import requests
from bs4 import BeautifulSoup

URL = "https://www.ikea.com/it/it/circular/second-hand/#/napoli?sort=id-desc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
}

def test_nuova_struttura():
    print(f"--- Avvio scansione IKEA Napoli ---")
    
    try:
        response = requests.get(URL, headers=HEADERS, timeout=20)
        # Se l'HTML non contiene i prodotti, potrebbe essere necessario l'URL dell'API
        # ma proviamo prima a leggere l'HTML che hai fornito
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Cerchiamo tutti i tag <li> che hanno un'etichetta "online" o classi simili
        # Usiamo un selettore più flessibile basato sul tuo esempio
        prodotti = soup.find_all('li', {'aria-label': lambda x: x and 'online' in x})

        if not prodotti:
            print("⚠️ Nessun prodotto trovato con i selettori attuali.")
            print("Il sito potrebbe richiedere il caricamento dei dati tramite l'API circular-service.")
            return

        print(f"🚀 Trovati {len(prodotti)} prodotti!\n")

        for i, p in enumerate(prodotti, 1):
            try:
                # Estrazione Nome
                nome = p.find('span', class_='typography-heading-xs').get_text(strip=True)
                
                # Estrazione Descrizione (es: fodera per chaise-longue)
                desc = p.find('span', class_='text--lighter').get_text(strip=True)
                
                # Estrazione Prezzo Scontato (quello grande)
                prezzo_scontato = p.find('span', class_='price--medium').find('span', class_='price__integer').get_text(strip=True)
                
                # Estrazione Link (prendiamo l'href dall'unico tag <a> presente)
                link_parziale = p.find('a')['href']
                link_completo = f"https://www.ikea.com/it/it/circular/second-hand/{link_parziale}"

                print(f"{i}. 📦 {nome}")
                print(f"   📝 {desc}")
                print(f"   💰 Prezzo: €{prezzo_scontato}")
                print(f"   🔗 Link: {link_completo}")
                print("-" * 30)
                
            except Exception as e:
                print(f"{i}. Errore nell'estrazione dati: {e}")

    except Exception as e:
        print(f"❌ Errore di connessione: {e}")

if __name__ == "__main__":
    test_nuova_struttura()
