
import requests
import json

url = "http://localhost:11434/api/chat"

texte = """
Marie Curie a travaillé à Paris avec Pierre Curie sur la radioactivité.
"""

prompt = f"""
Tu es un système d'extraction d'informations.

Voici un exemple d'extraction correcte.

Texte :
Victor Hugo est né à Besançon.

Réponse :
{{
    "entites": [
        {{"nom": "Victor Hugo", "type": "PERSONNE"}},
        {{"nom": "Besançon", "type": "LIEU"}}
    ],
    "relations": [
        {{
            "source": "Victor Hugo",
            "relation": "est né à",
            "cible": "Besançon"
        }}
    ]
}}

Maintenant, applique la même méthode au texte suivant.

Règles :
- Identifie les personnes, les lieux et les sujets importants.
- N'invente aucune information.
- Utilise uniquement les informations justifiées par le texte.
- Retourne uniquement un JSON valide, sans commentaire.
- Respecte exactement la structure de l'exemple.

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
    "stream": False,
    "options": {
        "temperature": 0
    }
}

response = requests.post(url, json=payload, timeout=120)
response.raise_for_status()

texte_reponse = response.json()["message"]["content"]

print("Réponse du modèle :")
print(texte_reponse)

try:
    resultat = json.loads(texte_reponse)
    print("\nJSON valide !")
except json.JSONDecodeError:
    print("\nAttention : la réponse n'est pas un JSON valide.")
