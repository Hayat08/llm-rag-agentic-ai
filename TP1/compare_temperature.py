
import requests
import json

URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

texte = """
Alice Martin studied at Stanford University.
After graduating, she joined Google in 2018.
"""

prompt = f"""
Extract factual relations explicitly supported by the text.

Return only valid JSON with this structure:
{{
    "relations": [
        {{
            "subject": "entity",
            "relation": "relation_type",
            "object": "entity"
        }}
    ]
}}

Rules:
- Use only facts supported by the text.
- Do not invent relations.
- Use concise relation labels such as educated_at and employed_by.
- Do not add explanations or Markdown.

Text:
{texte}
"""


def extraire(temperature):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "seed": 42
        }
    }

    response = requests.post(URL, json=payload, timeout=120)
    response.raise_for_status()

    contenu = response.json()["message"]["content"]

    try:
        resultat = json.loads(contenu)
        json_valide = isinstance(resultat, dict) and isinstance(
            resultat.get("relations"), list
        )
    except json.JSONDecodeError:
        resultat = None
        json_valide = False

    return contenu, resultat, json_valide


for temperature in [0, 0.5, 1.0]:
    print("\n" + "=" * 50)
    print(f"TEMPÉRATURE : {temperature}")

    contenu, resultat, json_valide = extraire(temperature)

    print("\nRéponse du modèle :")
    print(contenu)

    print("\nJSON conforme à la structure attendue :", json_valide)
