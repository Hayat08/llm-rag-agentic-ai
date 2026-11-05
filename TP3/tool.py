"""Les 3 outils de l'agent (TP3).
Le retrieval du TP2 est réutilisé tel quel : il devient un outil que l'agent choisit d'appeler.
"""
import sys
from pathlib import Path

import requests

# On réutilise rag.py et llm.py du TP2 (ajouté EN FIN de sys.path : les fichiers du TP3 restent prioritaires)
sys.path.append(str(Path(__file__).parent.parent / "TP2"))
from rag import Index  # noqa: E402

_index = None


def get_index() -> Index:
    """Charge l'index du TP2 une seule fois."""
    global _index
    if _index is None:
        _index = Index()
    return _index


def search_cases(query: str, k: int = 5) -> list:
    """Outil 1 : cherche des affaires dans l'index du TP2 (chaque résultat contient son meilleur passage)."""
    return get_index().search_cases(query, k)


def read_case(case_id: str, query: str, k: int = 4) -> dict:
    """Outil 2 : lit une affaire = récupère ses passages les plus liés à la question.
    (On ne renvoie pas toute la décision : elle ne tiendrait pas dans le contexte d'un 1B.)"""
    passages = get_index().search_in_case(case_id, query, k)
    if not passages:
        raise ValueError(f"Affaire inconnue : {case_id}")
    return {"case_id": case_id, "passages": [p["text"] for p in passages]}


def external_search(query: str, k: int = 2) -> list:
    """Outil 3 (externe) : API de Wikipédia FR, sans clé. Retourne titre, url, extrait."""
    rep = requests.get(
        "https://fr.wikipedia.org/w/api.php",
        params={"action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": k,
                "prop": "extracts", "exintro": 1, "explaintext": 1, "exchars": 1200,
                "format": "json", "redirects": 1},
        headers={"User-Agent": "tp-agentic-rag/1.0 (projet etudiant)"},
        timeout=15,
    )
    rep.raise_for_status()
    pages = rep.json().get("query", {}).get("pages", {})
    pages = sorted(pages.values(), key=lambda p: p.get("index", 99))
    return [{"titre": p["title"], "url": "https://fr.wikipedia.org/wiki/" + p["title"].replace(" ", "_"),
             "texte": p.get("extract", "")} for p in pages if p.get("extract")]