import json

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from relations import NOMS_AUTORISES, description_pour_prompt

app = FastAPI(title="Extraction d'informations avec un LLM local")

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"
STRATEGIES = ["zero_shot", "prompt_ameliore", "few_shot", "decomposition"]


class ExtractionRequest(BaseModel):
    texte: str = Field(min_length=1)
    strategie: str = "prompt_ameliore"
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)


def appeler_ollama(prompt: str, temperature: float) -> str:
    """Envoie un prompt au modèle local Ollama.
    Paramètres de génération contrôlés : température choisie, seed fixe, contexte 4096."""

    try:
        reponse = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es un système d'extraction d'informations. "
                            "Tu réponds uniquement avec un objet JSON valide."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": temperature, "seed": 42, "num_ctx": 4096},
            },
            timeout=300,
        )
        reponse.raise_for_status()
        return reponse.json()["message"]["content"]

    except requests.RequestException as erreur:
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de contacter Ollama : {erreur}",
        )


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------
FORMAT_JSON = """
Retourne exactement un objet JSON de cette forme :
{
  "entities": [
    {"name": "nom exact tel qu'écrit dans le texte", "type": "PER"}
  ],
  "relations": [
    {"subject": "nom d'entité", "relation": "type de relation", "object": "nom d'entité"}
  ]
}
Types d'entités possibles : PER (personne), ORG (organisation), LOC (lieu), TIME (date), MISC (autre : œuvre, événement...), NUM (nombre).
Utilise des listes vides si aucune entité ou relation n'est trouvée.
"""

# Exemples few-shot 
EXEMPLES_FEW_SHOT = """
Exemple 1
Texte : Niklas Bergqvist (born 6 October 1962 in Stockholm), is a Swedish songwriter, producer and musician. His career started in 1984, as a founding member of the Synthpop band Shanghai.
JSON :
{"entities": [{"name": "Niklas Bergqvist", "type": "PER"}, {"name": "6 October 1962", "type": "TIME"}, {"name": "Stockholm", "type": "LOC"}, {"name": "Swedish", "type": "LOC"}, {"name": "Shanghai", "type": "ORG"}],
 "relations": [{"subject": "Niklas Bergqvist", "relation": "date_of_birth", "object": "6 October 1962"},
               {"subject": "Niklas Bergqvist", "relation": "citizenship", "object": "Swedish"},
               {"subject": "Niklas Bergqvist", "relation": "member_of", "object": "Shanghai"}]}

Exemple 2
Texte : Michelle Ferre's first acting experience was opposite Jackie Chan in the 1998 Hong Kong martial arts film Who Am I?.
JSON :
{"entities": [{"name": "Michelle Ferre", "type": "PER"}, {"name": "Jackie Chan", "type": "PER"}, {"name": "1998", "type": "TIME"}, {"name": "Hong Kong", "type": "LOC"}, {"name": "Who Am I", "type": "MISC"}],
 "relations": [{"subject": "Who Am I", "relation": "cast_member", "object": "Jackie Chan"},
               {"subject": "Who Am I", "relation": "cast_member", "object": "Michelle Ferre"},
               {"subject": "Who Am I", "relation": "publication_date", "object": "1998"},
               {"subject": "Who Am I", "relation": "country_of_origin", "object": "Hong Kong"}]}
"""


def instruction_avec_relations() -> str:
    """Consignes précises : liste fermée de relations + règles anti-invention."""
    return f"""Extrais uniquement les entités et les relations factuelles explicitement présentes dans le texte.
N'invente aucune information.

Relations autorisées (sens : sujet -> objet). N'utilise AUCUNE autre relation :
{description_pour_prompt()}

Règles :
- Une relation n'est retournée que si le texte la supporte clairement.
- Les noms (sujet, objet) doivent être copiés tels qu'ils apparaissent dans le texte (en anglais).
- Pas de supposition transformée en fait.
{FORMAT_JSON}"""


def construire_prompt(texte: str, strategie: str) -> str:
    """Construit le prompt selon la stratégie sélectionnée (une seule requête au LLM)."""

    if strategie == "zero_shot":
        # volontairement minimal : pas de liste de relations, pas d'exemple
        return f"""Extrais les entités et les relations factuelles du texte.
{FORMAT_JSON}
Texte :
{texte}"""

    if strategie == "prompt_ameliore":
        return f"{instruction_avec_relations()}\nTexte :\n{texte}"

    if strategie == "few_shot":
        return (f"{instruction_avec_relations()}\n{EXEMPLES_FEW_SHOT}\n"
                f"Maintenant, traite ce texte de la même façon.\nTexte :\n{texte}\nJSON :")

    raise HTTPException(status_code=400, detail="Stratégie inconnue.")


def prompt_decomposition_entites(texte: str) -> str:
    return f"""Étape 1 : liste toutes les entités du texte (personnes, organisations, lieux, dates, œuvres, événements).
Copie leur nom exactement comme dans le texte.

Retourne uniquement : {{"entities": [{{"name": "nom", "type": "PER, ORG, LOC, TIME, MISC ou NUM"}}]}}

Texte :
{texte}"""


def prompt_decomposition_relations(texte: str, entites: list) -> str:
    return f"""Étape 2 : à partir du texte et de la liste d'entités, identifie les relations factuelles entre ces entités.
Utilise uniquement des noms de la liste d'entités.

Relations autorisées (sens : sujet -> objet). N'utilise AUCUNE autre relation :
{description_pour_prompt()}

Une relation n'est retournée que si le texte la supporte clairement. N'invente rien.
Retourne uniquement : {{"relations": [{{"subject": "...", "relation": "...", "object": "..."}}]}}

Entités :
{json.dumps(entites, ensure_ascii=False)}

Texte :
{texte}"""


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------
def valider_json(contenu: str) -> dict:
    """Vérifie la structure du JSON produit par le modèle."""

    try:
        resultat = json.loads(contenu)
    except json.JSONDecodeError:
        # Tentative de récupération si le modèle ajoute du texte autour du JSON.
        debut = contenu.find("{")
        fin = contenu.rfind("}")

        if debut == -1 or fin == -1:
            raise HTTPException(
                status_code=502,
                detail="Le modèle n'a pas produit de JSON valide.",
            )

        try:
            resultat = json.loads(contenu[debut:fin + 1])
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail="Impossible de lire le JSON produit par le modèle.",
            )

    if not isinstance(resultat, dict):
        raise HTTPException(status_code=502, detail="Le résultat doit être un objet JSON.")

    if not isinstance(resultat.get("entities"), list):
        raise HTTPException(status_code=502, detail="Le champ 'entities' doit être une liste.")

    if not isinstance(resultat.get("relations"), list):
        raise HTTPException(status_code=502, detail="Le champ 'relations' doit être une liste.")

    for entite in resultat["entities"]:
        if not isinstance(entite, dict) or not all(
            isinstance(entite.get(cle), str) for cle in ("name", "type")
        ):
            raise HTTPException(status_code=502, detail="Une entité ne respecte pas le format attendu.")

    for relation in resultat["relations"]:
        if not isinstance(relation, dict) or not all(
            isinstance(relation.get(cle), str) for cle in ("subject", "relation", "object")
        ):
            raise HTTPException(status_code=502, detail="Une relation ne respecte pas le format attendu.")

    return resultat


def filtrer_relations(resultat: dict) -> tuple:
    """Garde seulement les relations de la liste autorisée. Retourne (résultat, relations_ignorées)."""
    gardees = [r for r in resultat["relations"] if r["relation"].strip().lower() in NOMS_AUTORISES]
    ignorees = [r for r in resultat["relations"] if r not in gardees]
    return {**resultat, "relations": gardees}, ignorees



# Extraction complète 

def extraire_texte(texte: str, strategie: str, temperature: float) -> tuple:
    """Retourne (résultat validé, relations ignorées car hors liste)."""
    if strategie not in STRATEGIES:
        raise HTTPException(status_code=400, detail="Stratégie inconnue.")

    if strategie == "decomposition":
        # appels : d'abord les entités, ensuite les relations entre ces entités
        brut_entites = appeler_ollama(prompt_decomposition_entites(texte), temperature)
        try:
            entites = json.loads(brut_entites).get("entities", [])
        except (json.JSONDecodeError, AttributeError):
            raise HTTPException(status_code=502, detail="Étape 1 : JSON invalide pour les entités.")

        brut_relations = appeler_ollama(prompt_decomposition_relations(texte, entites), temperature)
        try:
            relations = json.loads(brut_relations).get("relations", [])
        except (json.JSONDecodeError, AttributeError):
            raise HTTPException(status_code=502, detail="Étape 2 : JSON invalide pour les relations.")

        resultat = valider_json(json.dumps({"entities": entites, "relations": relations}))
    else:
        resultat = valider_json(appeler_ollama(construire_prompt(texte, strategie), temperature))

    if strategie == "zero_shot":      # pas de liste imposée : on ne filtre pas
        return resultat, []
    return filtrer_relations(resultat)


@app.get("/")
def accueil():
    return {"message": "API d'extraction opérationnelle"}


@app.post("/extract")
def extraire(demande: ExtractionRequest):
    resultat, ignorees = extraire_texte(demande.texte, demande.strategie, demande.temperature)

    return {
        "strategie": demande.strategie,
        "temperature": demande.temperature,
        "json_valide": True,
        "resultat": resultat,
        "relations_ignorees": ignorees,     # relations hors liste, retirées par le code
    }
