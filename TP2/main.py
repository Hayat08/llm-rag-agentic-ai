"""Backend FastAPI du TP2 : orchestration du RAG.

Lancer :  uvicorn main:app --reload
Endpoints :
  GET  /search?q=...&k=5   -> affaires les plus pertinentes
  POST /summary            -> résumé d'une affaire
  POST /ask                -> question sur une affaire (réponse + passages utilisés)
"""
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

    try:
        resume = appeler_llm(prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
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

    try:
        reponse = appeler_llm(prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"reponse": reponse, "passages": [{"id": f"P{i}", "texte": p["text"]}
                                             for i, p in enumerate(passages, start=1)]}
