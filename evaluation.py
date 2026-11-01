
import argparse
import json
import random
import re

from donnees import charger, texte_du_doc
from main import STRATEGIES, extraire_texte
from relations import NOMS


def normaliser(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def gold_du_doc(doc: dict) -> list:
    """Liste de (alias_sujet, nom_relation, alias_objet) pour les relations ciblées."""
    gold = []
    for lab in doc["labels"]:
        if lab["r"] not in NOMS:
            continue
        h = {normaliser(m["name"]) for m in doc["vertexSet"][lab["h"]]}
        t = {normaliser(m["name"]) for m in doc["vertexSet"][lab["t"]]}
        gold.append((h, NOMS[lab["r"]], t))
    return gold


def meme_entite(nom: str, alias: set) -> bool:
    """Tolérant : 'Schneider' ~ 'Willi Schneider' (l'un contient l'autre)."""
    nom = normaliser(nom)
    return any(nom == a or (len(nom) > 3 and (nom in a or a in nom)) for a in alias)


def correspond(pred: dict, gold: tuple, avec_relation: bool) -> bool:
    h, rel, t = gold
    ok = meme_entite(pred["subject"], h) and meme_entite(pred["object"], t)
    if avec_relation:
        ok = ok and normaliser(pred["relation"]) == rel
    return ok


def evaluer_un_doc(doc: dict, strategie: str, temperature: float) -> dict:
    texte = texte_du_doc(doc)
    gold = gold_du_doc(doc)
    texte_norm = normaliser(texte)

    try:
        resultat, ignorees = extraire_texte(texte, strategie, temperature)
    except Exception:
        # JSON invalide ou Ollama en erreur : échec de format
        return {"valide": False, "gold": len(gold)}

    # dédoublonnage des prédictions
    vues, preds = set(), []
    for r in resultat["relations"] + ignorees:
        cle = (normaliser(r["subject"]), normaliser(r["relation"]), normaliser(r["object"]))
        if cle not in vues:
            vues.add(cle)
            preds.append(r)

    res = {"valide": True, "gold": len(gold), "predites": len(preds), "hors_liste": len(ignorees),
           "inventees": sum(1 for r in preds if normaliser(r["subject"]) not in texte_norm
                            or normaliser(r["object"]) not in texte_norm)}
    for nom, avec_rel in (("paires", False), ("triplets", True)):
        res[nom + "_preds_ok"] = sum(any(correspond(p, g, avec_rel) for g in gold) for p in preds)
        res[nom + "_gold_ok"] = sum(any(correspond(p, g, avec_rel) for p in preds) for g in gold)
    return res


def prf(ok_preds, nb_preds, ok_gold, nb_gold):
    p = ok_preds / nb_preds if nb_preds else 0
    r = ok_gold / nb_gold if nb_gold else 0
    return p, r, (2 * p * r / (p + r) if p + r else 0)


def resumer(resultats: list) -> dict:
    n = len(resultats)
    valides = [r for r in resultats if r["valide"]]
    nb_preds = sum(r["predites"] for r in valides)
    nb_gold = sum(r["gold"] for r in resultats)         # un échec de format compte comme rappel nul
    out = {"json_valide": len(valides) / n,
           "hallucination": sum(r["inventees"] for r in valides) / nb_preds if nb_preds else 0,
           "hors_liste": sum(r["hors_liste"] for r in valides) / nb_preds if nb_preds else 0,
           "nb_relations": nb_preds / n}
    for nom in ("paires", "triplets"):
        p, r, f = prf(sum(x[nom + "_preds_ok"] for x in valides), nb_preds,
                      sum(x[nom + "_gold_ok"] for x in valides), nb_gold)
        out.update({f"{nom}_P": p, f"{nom}_R": r, f"{nom}_F1": f})
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--n", type=int, default=10, help="nombre de documents évalués")
    parser.add_argument("--temps", type=float, nargs="+", default=[0.0, 0.7])
    parser.add_argument("--strategies", nargs="+", default=STRATEGIES)
    args = parser.parse_args()

    docs = charger(args.split)
    random.seed(0)                       # mêmes documents pour toutes les stratégies
    echantillon = random.sample(docs, args.n)

    lignes = []
    for temperature in args.temps:
        for strategie in args.strategies:
            print(f"-> {strategie} (T={temperature}) ...", flush=True)
            res = [evaluer_un_doc(d, strategie, temperature) for d in echantillon]
            lignes.append({"strategie": strategie, "temperature": temperature, **resumer(res)})

    print(f"\nJeu : {args.split}, {args.n} documents")
    print(f"{'stratégie':<16}{'T':>4}{'JSON':>6} | {'paires P':>8}{'R':>6}{'F1':>6} | "
          f"{'triplets P':>10}{'R':>6}{'F1':>6} | {'halluc.':>7}{'hors liste':>11}{'#rel':>6}")
    for l in lignes:
        print(f"{l['strategie']:<16}{l['temperature']:>4}{l['json_valide']:>6.0%} | "
              f"{l['paires_P']:>8.2f}{l['paires_R']:>6.2f}{l['paires_F1']:>6.2f} | "
              f"{l['triplets_P']:>10.2f}{l['triplets_R']:>6.2f}{l['triplets_F1']:>6.2f} | "
              f"{l['hallucination']:>7.0%}{l['hors_liste']:>11.0%}{l['nb_relations']:>6.1f}")
    json.dump(lignes, open(f"resultats_evaluation_{args.split}.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(f"\nRésultats sauvegardés dans resultats_evaluation_{args.split}.json")
