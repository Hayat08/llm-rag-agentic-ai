
import requests
import json

url = "http://localhost:11434/api/chat"

texte = """
Marie Curie a travaillé à Paris avec Pierre Curie sur la radioactivité.
"""

prompt = f"""
Tu es un système d'extraction d'informations.

À partir du texte suivant, identifie :
1. Les entités : personnes, lieux et sujets importants.
2. Les relations entre ces entités.

Réponds uniquement avec un JSON valide ayant cette structure :
{{
    "entites": [
        {{
            "nom": "nom de l'entité",
            "type": "PERSONNE, LIEU ou SUJET"
        }}
    ],
    "relations": [
        {{
            "source": "entité de départ",
            "relation": "relation entre les entités",
            "cible": "entité d'arrivée"
        }}
    ]
}}

N'ajoute aucune information qui n'est pas justifiée par le texte.

Texte :
{texte}
"""

payload = {
    "model": "llama3.2:1b",
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "stream": False
}

response = requests.post(url, json=payload, timeout=120)

response.raise_for_status()

response= response.json()["message"]["content"]
print("la réponse du modele est :\n")
print(response)

try:
    resultat = json.loads(response)
    print("\nJSON valide !")
except json.JSONDecodeError:
    print("\nAttention : la réponse n'est pas un JSON valide.")