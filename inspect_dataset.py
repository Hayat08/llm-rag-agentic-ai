
import json
from pathlib import Path

DATA_DIR = Path("Re-DocRED-main/Re-DocRED-main/data")

fichier = DATA_DIR / "dev_revised.json"

with open(fichier, "r", encoding="utf-8") as f:
    donnees = json.load(f)

print("Type de données :", type(donnees).__name__)
print("Nombre de documents :", len(donnees))

if isinstance(donnees, list) and donnees:
    document = donnees[0]

    print("\nClés du premier document :")
    print(list(document.keys()))

    print("\nAperçu du premier document :")
    for cle, valeur in document.items():
        if isinstance(valeur, list):
            print(f"{cle}: liste de {len(valeur)} éléments")
            if valeur:
                print("  Premier élément :", repr(valeur[0])[:300])
        else:
            print(f"{cle}: {repr(valeur)[:300]}")
