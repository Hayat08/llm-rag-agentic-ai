# Scénario 1 : RAG simple (une seule recherche suffit)
**Question :** Quel est le délai de prescription de l'action en contestation d'un licenciement ?

1. **DECISION** — [1/6] search_cases — preuve documentaire nécessaire : recherche dans le corpus
2. **TOOL** — search_cases({query: 'licenciement', k: 5})
3. **OBSERVATION** — 5 résultats. Meilleurs : Cour de cassation - Chambre sociale - 1994-04-07 - n° 92-42.714 (score 6.0) ; Cour de cassation - Chambre sociale - 2018-05-16 - n° 16-18.830 (score 5.76)
4. **DECISION** — [2/6] answer — [corrigé par le code : requête déjà essayée] des preuves sont disponibles
5. **CHECK** — Preuves suffisantes : oui — preuves présentes : oui ; citations valides : oui ; mots de la réponse présents dans les sources : 47% ; phrases non soutenues par leur source : 0 ; juge LLM : cohérent

## Réponse
Le délai de prescription de l'action en contestation d'un licenciement est de cinq ans, comme indiqué dans la jurisprudence [P2] (Cour de cassation - Chambre sociale - 2018-04-11 - n° 17-10.547).

Avertissement : None

## Sources
- P1 (corpus) Cour de cassation - Chambre sociale - 2012-10-17 - n° 11-10.910 
- P2 (corpus) Cour de cassation - Chambre sociale - 2018-04-11 - n° 17-10.547 [cité]
- P3 (corpus) Cour de cassation - Chambre sociale - 2009-09-23 - n° 08-44.016 
- P4 (corpus) Cour de cassation - Chambre sociale - 2018-05-16 - n° 16-18.830 
- P5 (corpus) Cour de cassation - Chambre sociale - 1994-04-07 - n° 92-42.714 

Stats : `{"iterations": 2, "appels_llm": 4, "outils": ["search_cases"], "duree_s": 70.6}`