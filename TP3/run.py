"""Lance les 3 scénarios de test du TP3 et sauvegarde chaque trace dans traces/.

Lancer :  python run_scenarios.py          (Ollama doit tourner, TP2/data/cases.jsonl doit exister)
         python run_scenarios.py 2        (un seul scénario)
IMPORTANT : adaptez les questions à vos décisions (regardez ce que contient votre corpus).
"""
import json
import sys
from pathlib import Path

from agent import run_agent

SCENARIOS = {
    1: ("RAG simple (une seule recherche suffit)",
        "Un salarié peut-il être licencié pour faute grave en cas de harcèlement moral ?"),
    2: ("Recherche multi-étapes (trouver une affaire puis la lire)",
        "Dans l'affaire concernant un licenciement pour inaptitude, quels sont les motifs retenus par la cour ?"),
    3: ("Information insuffisante (corpus insuffisant -> requête différente ou API externe)",
        "Qu'est-ce que le principe de l'autorité de la chose jugée ?"),
}

Path("traces").mkdir(exist_ok=True)
a_lancer = [int(sys.argv[1])] if len(sys.argv) > 1 else list(SCENARIOS)

for n in a_lancer:
    titre, question = SCENARIOS[n]
    print(f"\n{'=' * 70}\nSCÉNARIO {n} : {titre}\nQuestion : {question}\n{'=' * 70}")
    lignes = [f"# Scénario {n} : {titre}", f"**Question :** {question}", ""]
    for e in run_agent(question):
        if e["type"] == "FINAL":
            lignes += ["", "## Réponse", e["texte"], "", f"Avertissement : {e['avertissement']}",
                       "", "## Sources"] + [f"- {s['id']} ({s['provenance']}) {s['titre']} {'[cité]' if s['cite'] else ''}"
                                            for s in e["sources"]] + ["", f"Stats : `{json.dumps(e['stats'], ensure_ascii=False)}`"]
            print("\nRÉPONSE :", e["texte"])
            print("STATS   :", e["stats"])
        else:
            ligne = f"{e['etape']}. {e['type']:<12} {e['texte']}"
            print(ligne)
            lignes.append(f"{e['etape']}. **{e['type']}** — {e['texte']}")
    Path(f"traces/scenario{n}.md").write_text("\n".join(lignes), encoding="utf-8")
print("\nTraces sauvegardées dans traces/")