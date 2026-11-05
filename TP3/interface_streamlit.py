"""Interface Streamlit du TP3 : affiche la trace de l'agent EN DIRECT.

Lancer :  streamlit run app_streamlit.py   (backend : uvicorn main:app --reload --port 8001)
"""
import json

import requests
import streamlit as st

API = "http://localhost:8001/agent"
ICONES = {"DECISION": "🧭", "TOOL": "🔧", "OBSERVATION": "👁️", "CHECK": "✅", "ERROR": "❌", "FINAL": "🏁"}

st.title("⚖️ Agentic RAG sur la jurisprudence")
question = st.text_input("Votre question juridique")

if st.button("Lancer l'agent", type="primary") and question:
    st.subheader("Trace d'exécution")
    zone_trace = st.container()
    final = None
    try:
        with requests.post(API, json={"question": question}, stream=True, timeout=600) as rep:
            rep.raise_for_status()
            for ligne in rep.iter_lines():          # une étape = une ligne JSON, affichée dès réception
                if not ligne:
                    continue
                e = json.loads(ligne)
                if e["type"] == "FINAL":
                    final = e
                else:
                    zone_trace.markdown(f"{ICONES.get(e['type'], '•')} **{e['etape']}. {e['type']}** — {e['texte']}")
    except requests.RequestException as err:
        st.error(f"Backend injoignable : {err}")

    if final:
        st.subheader("Réponse")
        if final.get("avertissement"):
            st.warning(final["avertissement"])
        st.write(final["texte"])

        st.subheader("Sources (provenance)")
        for s in final["sources"]:
            etiquette = "📚 Corpus" if s["provenance"] == "corpus" else "🌐 Externe"
            utilisee = " — cité" if s["cite"] else ""
            with st.expander(f"{s['id']} · {etiquette} · {s['titre']}{utilisee}"):
                st.write(s["texte"])
                if s.get("url"):
                    st.markdown(s["url"])

        st.caption(f"Itérations : {final['stats']['iterations']} · appels LLM : {final['stats']['appels_llm']} · "
                   f"outils : {final['stats']['outils']} · durée : {final['stats']['duree_s']} s")