"""Backend FastAPI du TP3 : lance l'agent et STREAME la trace (une ligne JSON par étape).

Lancer :  uvicorn main:app --reload --port 8001
"""
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import tools
from agent import run_agent

app = FastAPI(title="Agentic RAG jurisprudence")
tools.get_index()   # charge l'index du TP2 au démarrage


class Question(BaseModel):
    question: str = Field(min_length=3)


@app.post("/agent")
def lancer_agent(demande: Question):
    def flux():
        for evenement in run_agent(demande.question):
            yield json.dumps(evenement, ensure_ascii=False) + "\n"   # NDJSON
    return StreamingResponse(flux(), media_type="application/x-ndjson")