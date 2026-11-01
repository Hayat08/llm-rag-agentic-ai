
import requests
import json

url = "http://localhost:11434/api/chat"

texte = """
Marie Curie a travaillé à Paris avec Pierre Curie sur la radioactivité.
"""

prompt = f"""
Tu es un système spécialisé dans l'extraction d'informations à partir de textes.

Ta tâche :
1. Identifie toutes les personnes, les lieux et les sujets scientifiques
   explicitement mentionnés dans le texte.
2. Identifie uniquement les relations réellement exprimées par le texte.
3. N'invente aucune information et ne déduis pas de faits qui ne sont pas indiqués.
4. Utilise exactement les noms des entités tels qu'ils apparaissent dans le texte.
5. Si aucune relation n'est clairement identifiable, retourne une liste vide.

Respecte obligatoirement ce format JSON :
{{
    "entites": [
        {{
            "nom": "nom exact",
            "type": "PERSONNE, LIEU ou SUJET"
        }}
    ],
    "relations": [
        {{
            "source": "entité de départ",
            "relation": "relation explicitement exprimée",
            "cible": "entité d'arrivée"
        }}
    ]
}}

Retourne uniquement le JSON, sans explication ni bloc Markdown.

Texte à analyser :
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