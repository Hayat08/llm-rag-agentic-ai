"""Chargement de Re-DocRED (fichiers dev/test/train) et conversion en texte lisible."""
import json
import re
from pathlib import Path

# On teste plusieurs emplacements possibles du dossier data
CHEMINS = ["Re-DocRED-main/Re-DocRED-main/data"]


def charger(split: str = "dev") -> list:
    
    for chemin in CHEMINS:
        fichier = Path(chemin) / f"{split}_revised.json"
        if fichier.exists():
            return json.load(open(fichier, encoding="utf-8"))
    raise FileNotFoundError(f"{split}_revised.json introuvable (cherché dans {CHEMINS})")


def texte_du_doc(doc: dict) -> str:
    """Les documents sont tokenisés (liste de mots par phrase) : on les recolle."""
    texte = " ".join(" ".join(tokens) for tokens in doc["sents"])
    texte = re.sub(r"\s+([,.;:!?)])", r"\1", texte)   # pas d'espace avant la ponctuation
    texte = re.sub(r"\(\s+", "(", texte)
    return texte.replace(' " ', ' "')
