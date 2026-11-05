"""Agent RAG (TP3) : boucle explicite  décider -> outil -> observation -> décider ... -> vérifier -> répondre.

Choix de conception (simple et lisible, sans framework) :
  - le LLM choisit l'action (JSON) ; le CODE vérifie/corrige ce choix (un 1B se trompe souvent)
  - run_agent() est un GÉNÉRATEUR : chaque étape de la trace est émise dès qu'elle se produit
  - arrêt : réponse vérifiée, ou MAX_ITER atteint, ou erreur contrôlée
"""
import json
import re
import time

import tools
from llm import appeler_llm
from rag import tokeniser

MAX_ITER = 5          # condition d'arrêt : nombre max de décisions
MAX_PREUVES = 5       # nombre max de passages donnés au LLM pour répondre
ACTIONS = ["search_cases", "read_case", "external_search", "answer"]
NON_TROUVE = "Information non trouvée dans les sources."


# ---------------------------------------------------------------- état partagé
def nouvel_etat(question: str) -> dict:
    return {
        "query": question,
        "documents": [],          # affaires retrouvées par search_cases
        "affaires_lues": set(),   # case_id déjà lus avec read_case
        "preuves": [],            # passages (corpus ou externes) : {source, titre, texte, ...}
        "requetes": [],           # requêtes déjà envoyées au corpus
        "externe_utilise": False,
        "iterations": 0,
        "echecs": [],             # raisons des vérifications ratées
        "reponse": None,
        "verification": None,     # "ok" / "echec"
        "llm_calls": 0,
        "outils": [],
    }


def llm(etat: dict, prompt: str, **kwargs) -> str:
    """Appel LLM avec compteur (observabilité)."""
    etat["llm_calls"] += 1
    return appeler_llm(prompt, **kwargs)


def ajouter_preuves(etat: dict, nouvelles: list):
    """Ajoute des passages sans doublon."""
    deja = {(p["titre"], p["texte"][:80]) for p in etat["preuves"]}
    for p in nouvelles:
        if (p["titre"], p["texte"][:80]) not in deja:
            etat["preuves"].append(p)


# ---------------------------------------------------------------- décision
def decrire_etat(etat: dict) -> str:
    if etat["documents"]:
        docs = "\n".join(
            f"  {i}. id={d['case_id']} | {d['titre']} | {'lue' if d['case_id'] in etat['affaires_lues'] else 'non lue'}"
            for i, d in enumerate(etat["documents"], start=1))
    else:
        docs = "  (aucune affaire trouvée pour l'instant)"
    return (f"Affaires du corpus :\n{docs}\n"
            f"Passages de preuve disponibles : {len(etat['preuves'])}\n"
            f"Source externe déjà utilisée : {'oui' if etat['externe_utilise'] else 'non'}\n"
            f"Requêtes déjà essayées : {etat['requetes'] or 'aucune'}\n"
            f"Dernier échec de vérification : {etat['echecs'][-1] if etat['echecs'] else 'aucun'}")


def politique_par_defaut(etat: dict) -> tuple:
    """Règles de secours quand le LLM propose une action invalide. Ne propose jamais une recherche déjà faite."""
    q = etat["query"]
    non_lues = [d for d in etat["documents"] if d["case_id"] not in etat["affaires_lues"]]
    if not etat["preuves"]:
        if not etat["requetes"]:
            return "search_cases", q, "aucune preuve : recherche dans le corpus"
        if not etat["externe_utilise"]:
            return "external_search", q, "corpus sans résultat : source externe"
        return "answer", "", "plus aucune piste : réponse avec ce qui existe"
    if etat["echecs"]:
        if non_lues:
            return "read_case", non_lues[0]["case_id"], "vérification échouée : lire l'affaire la plus pertinente"
        if not etat["externe_utilise"]:
            return "external_search", q, "vérification échouée : essayer une source externe"
    return "answer", "", "des preuves sont disponibles"


def decider(etat: dict) -> tuple:
    """Le LLM choisit l'action suivante ; le code la valide. Retourne (action, argument, raison)."""
    prompt = f"""Tu es un agent de recherche juridique. Question de l'utilisateur :
« {etat['query']} »

État actuel :
{decrire_etat(etat)}

Actions possibles :
- search_cases : chercher dans le corpus de jurisprudence (argument = mots-clés)
- read_case : lire les passages d'une affaire trouvée (argument = id de l'affaire)
- external_search : chercher sur Wikipédia pour une notion générale (argument = requête)
- answer : répondre (seulement si des passages de preuve existent)

Réponds uniquement en JSON : {{"action": "...", "argument": "...", "raison": "une phrase courte"}}"""

    defaut = politique_par_defaut(etat)
    try:
        choix = json.loads(llm(etat, prompt, json_mode=True))
        action = choix.get("action")
        argument = str(choix.get("argument") or "").strip()
        raison = str(choix.get("raison") or "").strip() or "décision du LLM"
    except (RuntimeError, json.JSONDecodeError, AttributeError):
        return (*defaut[:2], "(LLM invalide) " + defaut[2])

    # ---- garde-fous : on corrige les décisions impossibles ou inutiles ----
    if action not in ACTIONS:
        return (*defaut[:2], "(action inconnue) " + defaut[2])

    if action == "search_cases":
        argument = argument or etat["query"]
        if argument.lower() in [r.lower() for r in etat["requetes"]]:
            return (*defaut[:2], "(requête déjà essayée) " + defaut[2])

    if action == "read_case":
        ids = [d["case_id"] for d in etat["documents"]]
        if argument.isdigit() and 1 <= int(argument) <= len(ids):   # le LLM donne parfois le numéro de la liste
            argument = ids[int(argument) - 1]
        if argument not in ids or argument in etat["affaires_lues"]:
            return (*defaut[:2], "(affaire invalide ou déjà lue) " + defaut[2])

    if action == "external_search":
        if etat["externe_utilise"]:
            return (*defaut[:2], "(source externe déjà utilisée) " + defaut[2])
        argument = argument or etat["query"]

    if action == "answer" and not etat["preuves"]:
        return (*defaut[:2], "(pas de preuve) " + defaut[2])

    return action, argument, raison


# ---------------------------------------------------------------- outils
def executer_outil(etat: dict, action: str, argument: str) -> tuple:
    """Exécute l'outil, met à jour l'état, retourne (appel affiché, observation)."""
    etat["outils"].append(action)

    if action == "search_cases":
        etat["requetes"].append(argument)
        resultats = tools.search_cases(argument, k=5)
        etat["documents"] = resultats + [d for d in etat["documents"]
                                         if d["case_id"] not in {r["case_id"] for r in resultats}]
        ajouter_preuves(etat, [{"source": "corpus", "titre": r["titre"], "case_id": r["case_id"],
                                "texte": r["passage"]} for r in resultats])
        if not resultats:
            return f"search_cases({{query: {argument!r}, k: 5}})", "0 résultat"
        meilleurs = " ; ".join(f"{r['titre']} (score {r['score']})" for r in resultats[:2])
        return (f"search_cases({{query: {argument!r}, k: 5}})",
                f"{len(resultats)} résultats. Meilleurs : {meilleurs}")

    if action == "read_case":
        lecture = tools.read_case(argument, etat["query"])
        etat["affaires_lues"].add(argument)
        titre = next((d["titre"] for d in etat["documents"] if d["case_id"] == argument), argument)
        ajouter_preuves(etat, [{"source": "corpus", "titre": titre, "case_id": argument, "texte": t}
                               for t in lecture["passages"]])
        return (f"read_case({{case_id: {argument!r}}})",
                f"{len(lecture['passages'])} passages lus dans « {titre} »")

    if action == "external_search":
        etat["externe_utilise"] = True
        resultats = tools.external_search(argument)
        ajouter_preuves(etat, [{"source": "externe", "titre": "Wikipédia : " + r["titre"], "url": r["url"],
                                "texte": r["texte"]} for r in resultats])
        return (f"external_search({{query: {argument!r}}})",
                f"{len(resultats)} page(s) Wikipédia : " + ", ".join(r["titre"] for r in resultats) if resultats
                else "0 résultat externe")


# ---------------------------------------------------------------- réponse + vérification
def preuves_courantes(etat: dict) -> list:
    return etat["preuves"][-MAX_PREUVES:]


def repondre(etat: dict) -> str:
    preuves = preuves_courantes(etat)
    sources = "\n\n".join(
        f"[P{i}] ({'jurisprudence' if p['source'] == 'corpus' else 'SOURCE EXTERNE'} - {p['titre']})\n{p['texte']}"
        for i, p in enumerate(preuves, start=1))
    prompt = f"""Sources disponibles :

{sources}

Question : {etat['query']}

Règles :
- Réponds en français, uniquement à partir des sources ci-dessus.
- Cite les sources utilisées entre crochets, par exemple [P1].
- Si une information vient d'une SOURCE EXTERNE, précise que ce n'est pas une décision de justice.
- Si la réponse n'est pas dans les sources, réponds exactement : « {NON_TROUVE} »
- N'invente rien."""
    return llm(etat, prompt)


def verifier(etat: dict, reponse: str) -> tuple:
    """3 contrôles : preuves présentes, réponse cohérente avec les passages, pas d'info non sourcée.
    Retourne (ok, texte de la trace)."""
    preuves = preuves_courantes(etat)
    controles, ok = [], True

    # 1. Présence de preuves + réponse réelle
    if not preuves or NON_TROUVE.lower()[:25] in reponse.lower():
        return False, "Preuves suffisantes : non (aucune preuve ou le modèle n'a pas trouvé la réponse)"
    controles.append("preuves présentes : oui")

    # 2. Citations valides : au moins une, et toutes existent
    cites = {int(n) for n in re.findall(r"\[P(\d+)\]", reponse)}
    valides = cites and all(1 <= n <= len(preuves) for n in cites)
    controles.append(f"citations valides : {'oui' if valides else 'non'}")
    ok = ok and bool(valides)

    # 3a. Recouvrement lexical : les mots de la réponse doivent se retrouver dans les passages cités
    cites_ok = [n for n in cites if 1 <= n <= len(preuves)] or list(range(1, len(preuves) + 1))
    texte_sources = " ".join(preuves[n - 1]["texte"] for n in cites_ok)
    mots_reponse = set(tokeniser(re.sub(r"\[P\d+\]", " ", reponse)))
    mots_sources = set(tokeniser(texte_sources))
    recouvrement = len(mots_reponse & mots_sources) / len(mots_reponse) if mots_reponse else 0
    controles.append(f"mots de la réponse présents dans les sources : {recouvrement:.0%}")
    ok = ok and recouvrement >= 0.4

    # 3b. Juge LLM : la réponse contient-elle une information absente des passages ?
    prompt = f"""Passages :
{texte_sources}

Réponse à contrôler :
{reponse}

La réponse contient-elle une information absente des passages ?
Réponds uniquement en JSON : {{"info_inventee": true ou false, "raison": "phrase courte"}}"""
    try:
        juge = json.loads(llm(etat, prompt, json_mode=True))
        inventee = bool(juge.get("info_inventee"))
        controles.append(f"juge LLM : {'info non sourcée détectée' if inventee else 'cohérent'}")
        ok = ok and not inventee
    except (RuntimeError, json.JSONDecodeError, AttributeError):
        controles.append("juge LLM : indisponible (ignoré)")

    return ok, "Preuves suffisantes : " + ("oui" if ok else "non") + " — " + " ; ".join(controles)


# ---------------------------------------------------------------- boucle principale
def run_agent(question: str):
    """Générateur : émet un événement de trace à chaque étape.
    Types : DECISION, TOOL, OBSERVATION, CHECK, ERROR, FINAL."""
    debut = time.time()
    etat = nouvel_etat(question)
    etape = 0

    def evt(type_, texte, **extra):
        nonlocal etape
        etape += 1
        return {"etape": etape, "type": type_, "texte": texte, **extra}

    def final(avertissement=None):
        preuves = preuves_courantes(etat)
        cites = {int(n) for n in re.findall(r"\[P(\d+)\]", etat["reponse"] or "")}
        sources = [{"id": f"P{i}", "provenance": p["source"], "titre": p["titre"],
                    "url": p.get("url"), "texte": p["texte"], "cite": i in cites}
                   for i, p in enumerate(preuves, start=1)]
        return evt("FINAL", etat["reponse"] or "Aucune réponse fiable trouvée.",
                   avertissement=avertissement, sources=sources,
                   stats={"iterations": etat["iterations"], "appels_llm": etat["llm_calls"],
                          "outils": etat["outils"], "duree_s": round(time.time() - debut, 1)})

    while etat["iterations"] < MAX_ITER:
        etat["iterations"] += 1
        action, argument, raison = decider(etat)
        yield evt("DECISION", f"[{etat['iterations']}/{MAX_ITER}] {action} — {raison}")

        # --- l'agent veut répondre : réponse puis vérification ---
        if action == "answer":
            if not etat["preuves"]:      # plus de piste et aucune preuve : arrêt contrôlé (pas de réponse inventée)
                yield evt("OBSERVATION", "Arrêt : aucune source disponible pour répondre")
                yield final("⚠️ Aucune source trouvée (corpus et source externe).")
                return
            try:
                etat["reponse"] = repondre(etat)
            except RuntimeError as e:
                yield evt("ERROR", f"Erreur LLM : {e}")
                break
            ok, detail = verifier(etat, etat["reponse"])
            etat["verification"] = "ok" if ok else "echec"
            yield evt("CHECK", detail)
            if ok:
                yield final()
                return
            etat["echecs"].append(detail)     # le prochain DECISION en tient compte
            continue

        # --- sinon : appel d'un outil (les erreurs sont visibles et gérées) ---
        try:
            appel, observation = executer_outil(etat, action, argument)
            yield evt("TOOL", appel)
            yield evt("OBSERVATION", observation)
        except Exception as e:
            yield evt("ERROR", f"Erreur de l'outil {action} : {e}")

    # --- condition d'arrêt : limite d'itérations (ou erreur LLM) ---
    yield evt("OBSERVATION", f"Arrêt : limite de {MAX_ITER} itérations atteinte")
    if etat["reponse"] is None and etat["preuves"]:
        try:
            etat["reponse"] = repondre(etat)
        except RuntimeError:
            pass
    yield final("⚠️ Réponse NON vérifiée : l'agent s'est arrêté avant d'avoir des preuves suffisantes.")