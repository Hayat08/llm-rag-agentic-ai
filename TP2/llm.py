"""Appel au LLM local (Ollama) - même modèle que le TP1."""
import os

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")   # ex : OLLAMA_MODEL=llama3.2:3b


def appeler_llm(prompt: str, systeme: str = "Tu es un assistant juridique rigoureux.",
                temperature: float = 0.0, json_mode: bool = False) -> str:
    """Envoie un prompt à Ollama et retourne le texte de la réponse."""
    corps = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # num_ctx : taille du contexte (les passages juridiques sont longs)
        "options": {"temperature": temperature, "seed": 42, "num_ctx": 4096},
    }
    if json_mode:
        corps["format"] = "json"   # force Ollama à produire du JSON

    try:
        rep = requests.post(OLLAMA_URL, json=corps, timeout=300)
        rep.raise_for_status()
        return rep.json()["message"]["content"]
    except requests.RequestException as e:
        raise RuntimeError(f"Impossible de contacter Ollama : {e}")
