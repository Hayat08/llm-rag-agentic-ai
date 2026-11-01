
import requests
import json

url = "http://localhost:11434/api/chat"
model = "llama3.2:1b"

texte = """
Marie Curie a travaillé à Paris avec Pierre Curie sur la radioactivité.
"""


def appeler_llm(prompt):
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0}
    }

    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()

    return response.json()["message"]["content"]


# Étape 1 : extraire les entités
prompt_entites = f"""
Identifie les personnes, les lieux et les sujets importants
explicitement mentionnés dans le texte.

Réponds uniquement avec un JSON valide sous cette forme :
{{
    "entites": [
        {{"nom": "nom exact", "type": "PERSONNE, LIEU ou SUJET"}}
    ]
}}

Texte :
{texte}
"""

reponse_entites = appeler_llm(prompt_entites)
print("Étape 1 - Entités :")
print(reponse_entites)

try:
    donnees_entites = json.loads(reponse_entites)
except json.JSONDecodeError:
    raise ValueError("Le modèle n'a pas produit un JSON valide pour les entités.")


# Étape 2 : extraire les relations
prompt_relations = f"""
À partir du texte original et de la liste d'entités ci-dessous,
identifie les relations explicitement exprimées dans le texte.

N'invente aucune relation.
Utilise les noms exacts des entités fournies.
Si une relation n'est pas clairement établie, ne l'ajoute pas.

Réponds uniquement avec un JSON valide sous cette forme :
{{
    "relations": [
        {{
            "source": "entité de départ",
            "relation": "relation exprimée dans le texte",
            "cible": "entité d'arrivée"
        }}
    ]
}}

Texte original :
{texte}

Entités extraites :
{json.dumps(donnees_entites, ensure_ascii=False)}
"""

reponse_relations = appeler_llm(prompt_relations)
print("\nÉtape 2 - Relations :")
print(reponse_relations)

try:
    donnees_relations = json.loads(reponse_relations)
except json.JSONDecodeError:
    raise ValueError("Le modèle n'a pas produit un JSON valide pour les relations.")


# Combiner les résultats
resultat_final = {
    "entites": donnees_entites["entites"],
    "relations": donnees_relations["relations"]
}

print("\nRésultat final :")
print(json.dumps(resultat_final, ensure_ascii=False, indent=2))
