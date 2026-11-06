# Scénario 3 : Information insuffisante (corpus insuffisant -> requête différente ou API externe)
**Question :** Qui était Portalis et quel rôle a-t-il joué dans la rédaction du Code Napoléon ?

1. **DECISION** — [1/6] search_cases — preuve documentaire nécessaire : recherche dans le corpus
2. **TOOL** — search_cases({query: 'portalis', k: 5})
3. **OBSERVATION** — 0 résultat
4. **DECISION** — [2/6] external_search — [corrigé par le code : requête déjà essayée] corpus sans résultat : source externe
5. **TOOL** — external_search({query: 'Portalis Code Napoléon'})
6. **OBSERVATION** — 2 page(s) Wikipédia : Jean-Étienne-Marie Portalis, Code civil (France)
7. **DECISION** — [3/6] answer — [corrigé par le code : requête déjà essayée] des preuves sont disponibles
8. **CHECK** — Preuves suffisantes : oui — preuves présentes : oui ; citations valides : oui ; mots de la réponse présents dans les sources : 97% ; phrases non soutenues par leur source : 0 ; juge LLM : cohérent ; citations ajoutées par le code : 2

## Réponse
Jean-Étienne-Marie Portalis, dit Portalis l'Ancien, était un avocat, jurisconsulte, philosophe du droit et homme d'État français [P1].

Il a été sous Napoléon l'un des rédacteurs du Code civil des Français de 1804, avec les juristes Tronchet, Bigot de Préameneu et Maleville, qui institue une « législation uniforme, sorte de synthèse du droit d'Ancien Régime et des idées nouvelles » de la Révolution de 1789 [P1].

Avertissement : None

## Sources
- P1 (externe) Wikipédia : Jean-Étienne-Marie Portalis [cité]
- P2 (externe) Wikipédia : Code civil (France) 

Stats : `{"iterations": 3, "appels_llm": 5, "outils": ["search_cases", "external_search"], "duree_s": 38.5}`