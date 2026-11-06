
import json
import sys
from pathlib import Path

from agent import run_agent

SCENARIOS = {
    1: ("RAG simple (une seule recherche suffit)",
        "Quel est le délai de prescription de l'action en contestation d'un licenciement ?"),
    2: ("Recherche multi-étapes (trouver une affaire puis la lire)",
        "Pourquoi la cour juge-t-elle un licenciement dépourvu de cause réelle et sérieuse en l'absence de recherche de reclassement ?"),
    3: ("Information insuffisante (corpus insuffisant -> requête différente ou API externe)",
        "Qui était Portalis et quel rôle a-t-il joué dans la rédaction du Code Napoléon ?"),
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