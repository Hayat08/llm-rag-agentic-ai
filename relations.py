"""Relations ciblées pour Re-DocRED.

Re-DocRED contient 95 types de relations (codes Wikidata : P17, P27...).
Un modèle de 1B ne peut pas les connaître toutes : on cible les 20 plus fréquentes
(~73 % des relations du jeu dev) et on les décrit dans le prompt.
Format : code -> (nom court utilisé par le LLM, description avec le SENS sujet -> objet)
"""
RELATIONS = {
    "P131":  ("located_in",           "lieu -> région/entité administrative qui le contient (Calgary -> Alberta)"),
    "P17":   ("country",              "lieu -> pays (Vancouver -> Canada)"),
    "P27":   ("citizenship",          "personne -> pays/nationalité (Duff Gibson -> Canadian)"),
    "P150":  ("contains",             "entité administrative -> région qu'elle contient (Canada -> British Columbia)"),
    "P800":  ("notable_work",         "personne -> œuvre importante (Jeff -> Mess of Blues)"),
    "P527":  ("has_part",             "ensemble -> partie (Southern Italy -> Apulia)"),
    "P361":  ("part_of",              "partie -> ensemble (Apulia -> Southern Italy)"),
    "P175":  ("performer",            "œuvre musicale -> interprète (Mess of Blues -> Jeff)"),
    "P577":  ("publication_date",     "œuvre -> date de publication (Song of Freedom -> 1936)"),
    "P1344": ("participant_of",       "personne/organisation -> événement auquel elle participe (Vietnam -> Cambodian-Vietnamese War)"),
    "P710":  ("participant",          "événement -> participant (World War II -> Royal Canadian Air Force)"),
    "P463":  ("member_of",            "personne -> organisation dont elle est membre (Ramey Idriss -> ASCAP)"),
    "P1001": ("applies_to_jurisdiction", "organisation/personne -> territoire sur lequel elle a autorité (Calgary City Council -> Calgary)"),
    "P495":  ("country_of_origin",    "œuvre -> pays d'origine (Song of Freedom -> England)"),
    "P569":  ("date_of_birth",        "personne -> date de naissance (Ramey Idriss -> 11 September 1911)"),
    "P161":  ("cast_member",          "film/émission -> acteur (Song of Freedom -> Paul Robeson)"),
    "P571":  ("inception",            "organisation/œuvre -> date de création (Roketsan -> 1988)"),
    "P264":  ("record_label",         "artiste -> maison de disques (Ayumi Hamasaki -> Avex Trax)"),
    "P206":  ("located_next_to_water","lieu -> mer/lac/fleuve voisin (Sweden -> Baltic Sea)"),
    "P30":   ("continent",            "pays/lieu -> continent (Cuba -> Latin America)"),
}

NOMS = {code: nom for code, (nom, _) in RELATIONS.items()}      # P17 -> country
NOMS_AUTORISES = set(NOMS.values())


def description_pour_prompt() -> str:
    """Liste des relations, une par ligne, à coller dans le prompt."""
    return "\n".join(f"- {nom} : {desc}" for nom, desc in RELATIONS.values())
