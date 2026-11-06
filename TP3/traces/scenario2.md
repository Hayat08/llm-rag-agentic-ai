# Scénario 2 : Recherche multi-étapes (trouver une affaire puis la lire)
**Question :** Pourquoi la cour juge-t-elle un licenciement dépourvu de cause réelle et sérieuse en l'absence de recherche de reclassement ?

1. **DECISION** — [1/6] search_cases — preuve documentaire nécessaire : recherche dans le corpus
2. **TOOL** — search_cases({query: "licenciement dépourvu de cause réelle et sérieuse en l'absence de recherche de reclassement", k: 5})
3. **OBSERVATION** — 5 résultats. Meilleurs : Cour de cassation - Chambre sociale - 2011-10-25 - n° 10-14.566 (score 36.6) ; Cour de cassation - Chambre sociale - 2019-11-20 - n° 18-21.757 (score 35.1)
4. **DECISION** — [2/6] read_case — question sur le raisonnement d'une décision : lire l'affaire
5. **TOOL** — read_case({case_id: '613727efcd5801467742e935'})
6. **OBSERVATION** — 4 passages lus dans « Cour de cassation - Chambre sociale - 2011-10-25 - n° 10-14.566 »
7. **DECISION** — [3/6] answer — [corrigé par le code : requête déjà essayée] des preuves sont disponibles
8. **CHECK** — Preuves suffisantes : oui — preuves présentes : oui ; citations valides : oui ; mots de la réponse présents dans les sources : 83% ; phrases non soutenues par leur source : 0 ; juge LLM : cohérent ; citations ajoutées par le code : 3

## Réponse
La cour d'appel a jugé un licenciement dépourvu de cause réelle et sérieuse en l'absence de recherche de reclassement, car l'employeur n'a pas proposé les postes disponibles de même nature que celui que le salarié a auparavant refusé en réponse à une proposition de modification de son contrat de travail [P4].

La cour d'appel a également constaté que l'employeur avait, dès le 19 juillet 2006, à titre de reclassement, réitéré la proposition de réduction du temps de travail refusée une première fois par la salariée, sans tirer toutes les conséquences qui s'évinçaient de ses propres constatations [P5].

Enfin, la cour d'appel a estimé que le licenciement était dépourvu de cause réelle et sérieuse, sans à aucun moment s'expliquer sur les raisons qui l'ont motivé [P2].

Avertissement : None

## Sources
- P1 (corpus) Cour de cassation - Chambre sociale - 2017-04-27 - n° 15-15.840 
- P2 (corpus) Cour de cassation - Chambre sociale - 2009-09-23 - n° 08-44.016 [cité]
- P3 (corpus) Cour de cassation - Chambre sociale - 2019-11-20 - n° 18-21.757 
- P4 (corpus) Cour de cassation - Chambre sociale - 2011-10-25 - n° 10-14.566 [cité]
- P5 (corpus) Cour de cassation - Chambre sociale - 2011-10-25 - n° 10-14.566 [cité]

Stats : `{"iterations": 3, "appels_llm": 5, "outils": ["search_cases", "read_case"], "duree_s": 132.0}`