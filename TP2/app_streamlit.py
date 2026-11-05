"""Interface Streamlit du TP2 : recherche -> sélection -> résumé -> questions.

Lancer :  streamlit run app_streamlit.py   (backend : uvicorn main:app --reload)
"""
import requests
import streamlit as st

API = "http://localhost:8000"
st.title("⚖️ RAG sur la jurisprudence")


def appel(methode, chemin, **kwargs):
    """Appelle le backend et affiche proprement les erreurs."""
    try:
        rep = requests.request(methode, API + chemin, timeout=300, **kwargs)
        if rep.status_code != 200:
            st.error(f"Erreur {rep.status_code} : {rep.json().get('detail')}")
            return None
        return rep.json()
    except requests.RequestException as e:
        st.error(f"Backend injoignable : {e}")
        return None


# État conservé entre les interactions
st.session_state.setdefault("resultats", [])
st.session_state.setdefault("affaire", None)   # {case_id, titre}
st.session_state.setdefault("resume", None)
st.session_state.setdefault("chat", [])

# ---------- 1. Recherche ----------
st.header("1. Rechercher une affaire")
requete = st.text_input("Mots-clés ou question", "licenciement abusif harcèlement moral")
if st.button("Rechercher"):
    data = appel("GET", "/search", params={"q": requete, "k": 5})
    if data:
        st.session_state.resultats = data["resultats"]

for r in st.session_state.resultats:
    with st.container(border=True):
        st.markdown(f"**{r['titre']}**  (score {r['score']})")
        st.caption(r["extrait"] + "...")
        if st.button("Sélectionner", key=r["case_id"]):
            st.session_state.affaire = {"case_id": r["case_id"], "titre": r["titre"]}
            st.session_state.resume = None
            st.session_state.chat = []

# ---------- 2. Résumé ----------
affaire = st.session_state.affaire
if affaire:
    st.header("2. Résumé")
    st.info(f"Affaire sélectionnée : {affaire['titre']}")
    if st.button("Résumer l'affaire"):
        data = appel("POST", "/summary", json={"case_id": affaire["case_id"]})
        if data:
            st.session_state.resume = data["resume"]
    if st.session_state.resume:
        st.write(st.session_state.resume)

    # ---------- 3. Questions ----------
    st.header("3. Poser une question sur l'affaire")
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.write(msg["contenu"])
            if msg.get("passages"):
                with st.expander("Passages utilisés"):
                    for p in msg["passages"]:
                        st.markdown(f"**{p['id']}** — {p['texte']}")

    question = st.chat_input("Votre question sur cette décision")
    if question:
        st.session_state.chat.append({"role": "user", "contenu": question})
        data = appel("POST", "/ask", json={"case_id": affaire["case_id"], "question": question})
        if data:
            st.session_state.chat.append({"role": "assistant", "contenu": data["reponse"],
                                          "passages": data["passages"]})
        st.rerun()
