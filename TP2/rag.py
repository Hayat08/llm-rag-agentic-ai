"""Couche d'indexation et de retrieval du TP2 (lexical BM25).

Stratégie :
  - chaque décision est découpée en chunks (~1000 caractères, léger chevauchement)
  - un index BM25 est construit sur tous les chunks
  - recherche d'affaires : on cherche les meilleurs chunks, puis on garde le meilleur chunk par affaire
  - question sur UNE affaire : mini-index BM25 sur les chunks de cette affaire seulement
"""
import json
import re
import unicodedata
from pathlib import Path

from rank_bm25 import BM25Okapi

DATA_FILE = Path(__file__).parent / "data" / "cases.jsonl"
TAILLE_CHUNK = 1000
CHEVAUCHEMENT = 150

STOPWORDS = set("""le la les un une des de du et en au aux ce ces cet cette que qui quoi dont
ou où par pour sur dans avec sans sous son sa ses leur leurs il elle ils elles est sont
a ont été etre être fait faire pas ne se si plus mais comme aussi""".split())


def tokeniser(texte: str) -> list:
    """minuscules, sans accents, mots de plus de 2 lettres, sans mots vides."""
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return [m for m in re.findall(r"\w+", texte) if len(m) > 2 and m not in STOPWORDS]


def decouper(texte: str) -> list:
    """Découpe un texte en chunks de ~TAILLE_CHUNK caractères (coupe sur un espace)."""
    chunks, debut = [], 0
    while debut < len(texte):
        fin = min(debut + TAILLE_CHUNK, len(texte))
        if fin < len(texte):
            espace = texte.rfind(" ", debut, fin)
            fin = espace if espace > debut else fin
        chunks.append(texte[debut:fin].strip())
        if fin >= len(texte):
            break
        debut = max(fin - CHEVAUCHEMENT, debut + 1)
    return [c for c in chunks if c]


def titre_affaire(cas: dict) -> str:
    """Titre lisible construit à partir des métadonnées."""
    morceaux = [cas.get("jurisdiction"), cas.get("chamber"), cas.get("decision_date"),
                f"n° {cas['number']}" if cas.get("number") else None]
    return " - ".join(str(m) for m in morceaux if m) or str(cas["id"])


class Index:
    def __init__(self, fichier: Path = DATA_FILE):
        self.cas = {}          # case_id -> dict (texte + métadonnées)
        self.chunks = []       # liste de {case_id, num, text}
        self.chunks_par_cas = {}

        for ligne in open(fichier, encoding="utf-8"):
            c = json.loads(ligne)
            self.cas[c["id"]] = c
            self.chunks_par_cas[c["id"]] = []
            for num, morceau in enumerate(decouper(c["text"])):
                self.chunks.append({"case_id": c["id"], "num": num, "text": morceau})
                self.chunks_par_cas[c["id"]].append(len(self.chunks) - 1)

        if not self.chunks:
            raise SystemExit("data/cases.jsonl est vide : relance 'python prepare_data.py --n 2000' "
                             "et vérifie qu'il affiche bien des décisions sauvegardées.")
        self.bm25 = BM25Okapi([tokeniser(ch["text"]) for ch in self.chunks])

    # ---- 1. Recherche d'affaires ----
    def search_cases(self, query: str, k: int = 5) -> list:
        scores = self.bm25.get_scores(tokeniser(query))
        ordre = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:300]
        resultats = {}
        for i in ordre:
            ch = self.chunks[i]
            if scores[i] <= 0 or ch["case_id"] in resultats:
                continue        # on garde seulement le meilleur chunk de chaque affaire
            cas = self.cas[ch["case_id"]]
            resultats[ch["case_id"]] = {
                "case_id": ch["case_id"], "titre": titre_affaire(cas),
                "score": round(float(scores[i]), 2),
                "solution": cas.get("solution"), "extrait": ch["text"][:300],
                "passage": ch["text"],   # chunk complet (utilisé comme preuve par l'agent du TP3)
            }
            if len(resultats) >= k:
                break
        return list(resultats.values())

    # ---- 2. Lecture / questions sur une affaire ----
    def passages_affaire(self, case_id: str) -> list:
        """Tous les chunks d'une affaire (dans l'ordre)."""
        return [self.chunks[i] for i in self.chunks_par_cas.get(case_id, [])]

    def search_in_case(self, case_id: str, query: str, k: int = 4) -> list:
        """Les k chunks de l'affaire les plus proches de la question."""
        passages = self.passages_affaire(case_id)
        if not passages:
            return []
        bm25 = BM25Okapi([tokeniser(p["text"]) for p in passages])
        scores = bm25.get_scores(tokeniser(query))
        meilleurs = sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)[:k]
        # on remet dans l'ordre du texte pour garder la logique du document
        return [passages[i] for i in sorted(meilleurs)]

    def passages_pour_resume(self, case_id: str) -> list:
        """Début (faits, procédure) + fin (décision) de la décision."""
        passages = self.passages_affaire(case_id)
        if len(passages) <= 5:
            return passages
        return passages[:3] + passages[-2:]
