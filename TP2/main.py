
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm import appeler_llm
from rag import Index, titre_affaire

app = FastAPI(title="RAG jurisprudence")
index = Index()   # chargé une seule fois au démarrage (quelques secondes)

PAS_DE_REPONSE = "Information non trouvée dans la décision."


class ResumeRequest(BaseModel):
    case_id: str


class QuestionRequest(BaseModel):
    case_id: str
    question: str
    k: int = 4


def verifier_affaire(case_id: str):
    if case_id not in index.cas:
        raise HTTPException(status_code=404, detail="Affaire inconnue.")


def formater_passages(passages: list) -> str:
    """[P1] texte... [P2] texte... : le LLM pourra citer ces numéros."""
    return "\n\n".join(f"[P{i}] {p['text']}" for i, p in enumerate(passages, start=1))


def generer(prompt: str, max_tokens: int = 300) -> str:
    """Appelle le LLM. Les erreurs sont visibles : 503 si Ollama est injoignable, 502 si la réponse est vide."""
    debut = time.time()
    try:
        reponse = appeler_llm(prompt, max_tokens=max_tokens)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    print(f"[LLM] réponse en {time.time() - debut:.1f} s ({len(prompt)} caractères envoyés)", flush=True)
    if not reponse.strip():
        raise HTTPException(status_code=502, detail="Le modèle a renvoyé une réponse vide. Réessaie.")
    return reponse


@app.get("/search")
def rechercher(q: str, k: int = 5):
    return {"query": q, "resultats": index.search_cases(q, k)}


@app.post("/summary")
def resumer(demande: ResumeRequest):
    verifier_affaire(demande.case_id)
    passages = index.passages_pour_resume(demande.case_id)

    prompt = f"""Voici des extraits d'une décision de justice.

{formater_passages(passages)}

Rédige un résumé en français avec exactement ces trois rubriques :
Faits : ...
Procédure : ...
Décision : ...

Règles :
- Utilise uniquement les informations présentes dans les extraits.
- Si une rubrique n'est pas dans les extraits, écris « Non précisé dans les extraits ».
- N'invente ni noms, ni dates, ni montants."""

    resume = generer(prompt, max_tokens=350)
    return {"case_id": demande.case_id, "titre": titre_affaire(index.cas[demande.case_id]), "resume": resume}


@app.post("/ask")
def poser_question(demande: QuestionRequest):
    verifier_affaire(demande.case_id)
    passages = index.search_in_case(demande.case_id, demande.question, demande.k)

    prompt = f"""Passages de la décision :

{formater_passages(passages)}

Question : {demande.question}

Règles :
- Réponds en français, uniquement à partir des passages ci-dessus.
- Indique les passages utilisés entre crochets, par exemple [P1].
- Si la réponse n'est pas dans les passages, réponds exactement : « {PAS_DE_REPONSE} »
- N'invente rien."""

    reponse = generer(prompt, max_tokens=250)
    return {"reponse": reponse, "passages": [{"id": f"P{i}", "texte": p["text"]}
                                             for i, p in enumerate(passages, start=1)]}