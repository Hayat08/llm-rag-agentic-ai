
import json
import re
import time

import tools
from llm import appeler_llm
from rag import tokeniser

MAX_ITER = 6          # condition d'arrêt : nombre max de décisions
MAX_PREUVES = 5       # nombre max de passages donnés au LLM pour répondre
ACTIONS = ["search_cases", "read_case", "external_search", "answer"]
NON_TROUVE = "Information non trouvée dans les sources."
MOTS_QUESTION_DETAILLEE = ("pourquoi", "motif", "raisonnement", "dans l'affaire", "quels sont les faits", "que décide")


# ---------------------------------------------------------------- état partagé
def nouvel_etat(question: str) -> dict:
    return {
        "query": question,
        "documents": [],          # affaires retrouvées par search_cases
        "affaires_lues": set(),   # case_id déjà lus avec read_case
        "preuves": [],            # passages  {source, titre ..}
        "requetes": [],           # requêtes déjà envoyées au corpus
        "externe_utilise": False,
        "iterations": 0,
        "echecs": [],             # raisons des vérifications ratées
        "preuves_a_l_echec": -1,  # nb de preuves au dernier échec 
        "reponse": None,
        "verification": None,     # "ok" / "echec"
        "llm_calls": 0,
        "outils": [],
    }


def llm(etat: dict, prompt: str, **kwargs) -> str:
    
    etat["llm_calls"] += 1
    return appeler_llm(prompt, **kwargs)


def ajouter_preuves(etat: dict, nouvelles: list):
    
    deja = {(p["titre"], p["texte"][:80]) for p in etat["preuves"]}
    for p in nouvelles:
        if (p["titre"], p["texte"][:80]) not in deja:
            etat["preuves"].append(p)


#  décision
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
        # 0) de nouvelles preuves sont arrivées depuis le dernier échec : on retente la réponse
        if len(etat["preuves"]) > etat["preuves_a_l_echec"]:
            return "answer", "", "nouvelles preuves : nouvelle tentative de réponse"
        # 1) reformuler : la requête du LLM était peut-être trop courte -> on cherche avec la question complète
        if q not in etat["requetes"]:
            return "search_cases", q, "vérification échouée : nouvelle recherche avec la question complète"
        # 2) « non trouvé », 2 échecs ou rien à lire : le corpus ne suffit probablement pas -> source externe
        pas_trouve = "pas trouvé" in etat["echecs"][-1]      # le modèle dit que les sources ne contiennent pas la réponse
        if not etat["externe_utilise"] and (len(etat["echecs"]) >= 2 or not non_lues or pas_trouve):
            return "external_search", q, "le corpus ne suffit pas : essayer une source externe"
        # 3) lire UNE affaire (pas toutes : on garde des itérations pour la suite)
        if non_lues and not etat["affaires_lues"]:
            return "read_case", non_lues[0]["case_id"], "vérification échouée : lire l'affaire la plus pertinente"
        # 4) source externe
        if not etat["externe_utilise"]:
            return "external_search", q, "vérification échouée : essayer une source externe"
        if non_lues:
            return "read_case", non_lues[0]["case_id"], "vérification échouée : lire une autre affaire"
    return "answer", "", "des preuves sont disponibles"


def decider(etat: dict) -> tuple:
    
    action, argument, raison = decider_brut(etat)
    if (action == "answer" and etat["documents"] and not etat["affaires_lues"]
            and any(m in etat["query"].lower() for m in MOTS_QUESTION_DETAILLEE)):
        return "read_case", etat["documents"][0]["case_id"], "question sur le raisonnement d'une décision : lire l'affaire"
    return action, argument, raison


def decider_brut(etat: dict) -> tuple:
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

Réponds uniquement en JSON : {{"action": "...", "argument": "...", "raison": "pourquoi cette action, sans répondre à la question"}}"""

    defaut = politique_par_defaut(etat)
    try:
        choix = json.loads(llm(etat, prompt, json_mode=True, max_tokens=120))
        action = choix.get("action")
        argument = str(choix.get("argument") or "").strip()
        raison = str(choix.get("raison") or "").strip() or "décision du LLM"
    except (RuntimeError, json.JSONDecodeError, AttributeError):
        return (*defaut[:2], "[corrigé par le code : LLM invalide] " + defaut[2])

    #  on corrige les décisions impossibles ou inutile
    if action not in ACTIONS:
        return (*defaut[:2], "[corrigé par le code : action inconnue] " + defaut[2])

    if action == "search_cases":
        argument = argument or etat["query"]
        if argument.lower() in [r.lower() for r in etat["requetes"]]:
            return (*defaut[:2], "[corrigé par le code : requête déjà essayée] " + defaut[2])
        if etat["echecs"]:   # après un échec, une requête sans rapport avec la QUESTION vient souvent d'une réponse inventée
            mq, ma = set(tokeniser(etat["query"])), set(tokeniser(argument))
            if not ma or len(ma & mq) / len(ma) < 0.5:
                return (*defaut[:2], "[corrigé par le code : requête sans rapport avec la question] " + defaut[2])

    if action == "read_case":
        ids = [d["case_id"] for d in etat["documents"]]
        if argument.isdigit() and 1 <= int(argument) <= len(ids):   # le LLM donne parfois le numéro de la liste
            argument = ids[int(argument) - 1]
        if argument not in ids or argument in etat["affaires_lues"]:
            return (*defaut[:2], "[corrigé par le code : affaire invalide ou déjà lue] " + defaut[2])

    if action == "external_search":
        if etat["externe_utilise"]:
            return (*defaut[:2], "[corrigé par le code : source externe déjà utilisée] " + defaut[2])
        argument = argument or etat["query"]

    if action == "answer" and not etat["preuves"]:
        return (*defaut[:2], "[corrigé par le code : pas de preuve] " + defaut[2])

    if action == "answer" and etat["echecs"] and len(etat["preuves"]) <= etat["preuves_a_l_echec"]:
        return (*defaut[:2], "[corrigé par le code : rien de nouveau depuis l'échec] " + defaut[2])

    # La "raison" écrite contient souvent une réponse inventée : on affiche une justification du code.
    raisons = {"search_cases": "preuve documentaire nécessaire : recherche dans le corpus",
               "read_case": "lire les passages de l'affaire la plus pertinente",
               "external_search": "notion hors corpus : source externe",
               "answer": "des preuves sont disponibles : réponse puis vérification"}
    return action, argument, raisons[action]


# outils
def executer_outil(etat: dict, action: str, argument: str) -> tuple:
    """Exécute l'outil, met à jour l'état, retourne (appel affiché, observation)."""
    etat["outils"].append(action)

    if action == "search_cases":
        etat["requetes"].append(argument)
        resultats = tools.search_cases(argument, k=5)
        etat["documents"] = resultats + [d for d in etat["documents"]
                                         if d["case_id"] not in {r["case_id"] for r in resultats}]
        # le meilleur résultat est ajouté EN DERNIER, donc il reste dans les 5 preuves envoyées au LLM
        ajouter_preuves(etat, [{"source": "corpus", "titre": r["titre"], "case_id": r["case_id"],
                                "texte": r["passage"]} for r in reversed(resultats)])
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
        argument = requete_externe(argument)       # noms propres de la question
        resultats = tools.external_search(argument)
        ajouter_preuves(etat, [{"source": "externe", "titre": "Wikipédia : " + r["titre"], "url": r["url"],
                                "texte": r["texte"]} for r in resultats])
        return (f"external_search({{query: {argument!r}}})",
                f"{len(resultats)} page(s) Wikipédia : " + ", ".join(r["titre"] for r in resultats) if resultats
                else "0 résultat externe")


#  réponse + vérification
def preuves_courantes(etat: dict) -> list:
    """Les MAX_PREUVES passages les plus proches de la question (par recouvrement de mots), dans l'ordre d'arrivée.
    Un passage externe pertinent n'est donc pas chassé par des résultats de recherche hors sujet."""
    mots_q = set(tokeniser(etat["query"]))
    scores = [len(mots_q & set(tokeniser(p["texte"]))) / (len(mots_q) or 1) for p in etat["preuves"]]
    # en cas d'égalité, on préfère le passage le plus récent
    meilleurs = sorted(range(len(scores)), key=lambda i: (-scores[i], -i))[:MAX_PREUVES]
    return [etat["preuves"][i] for i in sorted(meilleurs)]


def requete_externe(texte: str) -> str:
    """Wikipédia comprend mal une phrase entière : on garde les noms propres (mots en majuscule hors début de phrase).
    Ex : « Qui était Portalis et quel rôle ... du Code Napoléon ? » -> « Portalis Code Napoléon »"""
    mots = re.findall(r"[\wÀ-ÿ'-]+", texte)
    noms = [m for m in mots[1:] if m[0].isupper()]
    return " ".join(noms) if noms else texte


def est_phrase_meta(phrase: str, mots: set) -> bool:
    """Phrase sans contenu factuel (ex : « cette information vient d'une source externe »)."""
    return len(mots) <= 8 and any(m in phrase.lower() for m in ("externe", "wikip", "décision de justice"))


def ajouter_citations_manquantes(reponse: str, preuves: list, seuil: float = 0.5) -> tuple:
    """Si le modèle oublie [P#] sur une phrase, on lui attribue le passage qui la soutient le mieux
    (recouvrement de mots >= seuil). Retourne (réponse, nombre de citations ajoutées)."""
    if not preuves:
        return reponse, 0
    morceaux = re.split(r"(?<=[.!?])(\s+)", reponse)          # phrases + séparateurs
    ajoutees = 0
    for i in range(0, len(morceaux), 2):
        phrase = morceaux[i]
        mots = set(tokeniser(phrase))
        if len(mots) < 4 or re.search(r"\[P\d+\]", phrase) or est_phrase_meta(phrase, mots):
            continue
        recouvrements = [len(mots & set(tokeniser(p["texte"]))) / len(mots) for p in preuves]
        meilleur = max(range(len(preuves)), key=lambda k: recouvrements[k])
        if recouvrements[meilleur] >= seuil:
            nu = phrase.rstrip()
            fin = nu[-1] if nu and nu[-1] in ".!?" else ""
            morceaux[i] = (nu[:-1] if fin else nu) + f" [P{meilleur + 1}]" + fin
            ajoutees += 1
    return "".join(morceaux), ajoutees


def phrases_non_soutenues(reponse: str, preuves: list, seuil: float = 0.35) -> list:
    """Pour chaque phrase de la réponse : ses mots doivent se retrouver dans le(s) passage(s) qu'elle cite
    (ou dans toutes les preuves si elle ne cite rien). Retourne les phrases insuffisamment soutenues."""
    faibles = []
    for phrase in re.split(r"(?<=[.!?])\s+|\n+", reponse):
        mots = set(tokeniser(re.sub(r"\[P\d+\]", " ", phrase)))
        if len(mots) < 4:                      # phrase trop courte pour être évaluée
            continue
        if est_phrase_meta(phrase, mots):
            continue                           # phrase "méta" (ex : « cette information vient d'une source externe »)
        cites = [int(n) for n in re.findall(r"\[P(\d+)\]", phrase) if 1 <= int(n) <= len(preuves)]
        sources = [preuves[n - 1] for n in cites] or preuves
        mots_sources = set()
        for p in sources:
            mots_sources |= set(tokeniser(p["texte"]))
        if len(mots & mots_sources) / len(mots) < seuil:
            faibles.append(phrase.strip()[:70])
    return faibles


def dedoublonner_phrases(reponse: str, seuil: float = 0.8) -> str:
    """Retire les phrases (quasi) identiques : un petit modèle répète parfois la même phrase plusieurs fois."""
    gardees, ensembles = [], []
    for phrase in re.split(r"(?<=[.!?])\s+|\n+", reponse):
        mots = set(tokeniser(re.sub(r"\[P\d+\]", " ", phrase)))
        if not phrase.strip():
            continue
        if mots and any(len(mots & m) / len(mots | m) >= seuil for m in ensembles):
            continue
        ensembles.append(mots)
        gardees.append(phrase.strip())
    return "\n\n".join(gardees)


def couper_phrase_incomplete(texte: str) -> str:
    """Si la génération a été coupée (limite de longueur), on retire la dernière phrase inachevée."""
    texte = texte.strip()
    if texte and texte[-1] not in ".!?]»":
        fin = max(texte.rfind(c) for c in ".!?")
        if fin > 0:
            return texte[:fin + 1]
    return texte


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
- Réponds en 4 phrases maximum, sans article de loi que les sources ne citent pas.
- N'invente rien."""
    return dedoublonner_phrases(couper_phrase_incomplete(llm(etat, prompt, max_tokens=350)))


def verifier(etat: dict, reponse: str) -> tuple:
    """3 contrôles : preuves présentes, réponse cohérente avec les passages, pas d'info non sourcée.
    Retourne (ok, texte de la trace)."""
    preuves = preuves_courantes(etat)
    controles, ok = [], True

    #  Présence de preuves + réponse réelle
    if not preuves or NON_TROUVE.lower()[:25] in reponse.lower():
        return False, "Preuves suffisantes : non (aucune preuve ou le modèle n'a pas trouvé la réponse)"
    controles.append("preuves présentes : oui")

    #  Citations valides : au moins une, et toutes existent
    cites = {int(n) for n in re.findall(r"\[P(\d+)\]", reponse)}
    valides = cites and all(1 <= n <= len(preuves) for n in cites)
    controles.append(f"citations valides : {'oui' if valides else 'non'}")
    ok = ok and bool(valides)

    #  Recouvrement lexical : les mots de la réponse doivent se retrouver dans les passages cités
    cites_ok = [n for n in cites if 1 <= n <= len(preuves)] or list(range(1, len(preuves) + 1))
    texte_sources = " ".join(preuves[n - 1]["texte"] for n in cites_ok)
    mots_reponse = set(tokeniser(re.sub(r"\[P\d+\]", " ", reponse)))
    mots_sources = set(tokeniser(texte_sources))
    recouvrement = len(mots_reponse & mots_sources) / len(mots_reponse) if mots_reponse else 0
    controles.append(f"mots de la réponse présents dans les sources : {recouvrement:.0%}")
    ok = ok and recouvrement >= 0.4

    #  Phrase par phrase : une phrase qui cite [P1] doit être appuyée par P1, pas par un autre passage
    faibles = phrases_non_soutenues(reponse, preuves)
    controles.append(f"phrases non soutenues par leur source : {len(faibles)}" +
                     (f" (ex : « {faibles[0]} »)" if faibles else ""))
    ok = ok and not faibles

    #  Juge LLM : la réponse contient-elle une information absente des passages ?
    prompt = f"""Passages :
{texte_sources}

Réponse à contrôler :
{reponse}

La réponse contient-elle une information absente des passages ?
Réponds uniquement en JSON : {{"info_inventee": true ou false, "raison": "phrase courte"}}"""
    try:
        juge = json.loads(llm(etat, prompt, json_mode=True, max_tokens=120))
        inventee = bool(juge.get("info_inventee"))
        controles.append(f"juge LLM : {'info non sourcée détectée' if inventee else 'cohérent'}")
        ok = ok and not inventee
    except (RuntimeError, json.JSONDecodeError, AttributeError):
        controles.append("juge LLM : indisponible (ignoré)")

    return ok, "Preuves suffisantes : " + ("oui" if ok else "non") + " — " + " ; ".join(controles)


#  boucle principale
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
        if etat["iterations"] == MAX_ITER and action != "answer" and etat["preuves"]:
            action, argument, raison = "answer", "", "dernière itération : on répond avec les preuves disponibles"
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
            etat["reponse"], nb_ajoutees = ajouter_citations_manquantes(etat["reponse"], preuves_courantes(etat))
            ok, detail = verifier(etat, etat["reponse"])
            if nb_ajoutees:
                detail += f" ; citations ajoutées par le code : {nb_ajoutees}"
            etat["verification"] = "ok" if ok else "echec"
            yield evt("CHECK", detail)
            if ok:
                yield final()
                return
            etat["echecs"].append(detail)     # le prochain DECISION en tient compte
            etat["preuves_a_l_echec"] = len(etat["preuves"])
            continue

        # --- sinon : appel d'un outil (les erreurs sont visibles et gérées) ---
        try:
            appel, observation = executer_outil(etat, action, argument)
            yield evt("TOOL", appel)
            yield evt("OBSERVATION", observation)
        except Exception as e:
            yield evt("ERROR", f"Erreur de l'outil {action} : {e}")

    #  condition d'arrêt : limite d'itérations 
    yield evt("OBSERVATION", f"Arrêt : limite de {MAX_ITER} itérations atteinte")
    if etat["reponse"] is None and etat["preuves"]:
        try:
            etat["reponse"] = repondre(etat)
        except RuntimeError:
            pass
    yield final(" Réponse NON vérifiée : l'agent s'est arrêté avant d'avoir des preuves suffisantes.")