
import random

import requests
import streamlit as st

from donnees import charger, texte_du_doc

API_URL = "http://localhost:8000/extract"

st.title("Extraction d'informations avec un petit LLM local")


@st.cache_data
def charger_exemples():
    """Textes du jeu dev de Re-DocRED, avec leurs relations gold (pour comparer à l'œil)."""
    try:
        return [(texte_du_doc(d), d) for d in charger("dev")[:50]]
    except FileNotFoundError:
        return []


exemples = charger_exemples()

# Menu de stratégie
strategie = st.sidebar.selectbox(
    "Stratégie de prompting",
    ["zero_shot", "prompt_ameliore", "few_shot", "decomposition"],
    index=1,
)
temperature = st.sidebar.slider("Température", 0.0, 1.0, 0.0, 0.1)

# --- Saisie du texte ---
if "texte" not in st.session_state:
    st.session_state.texte = "Alice Martin studied at Stanford University. After graduating, she joined Google in 2018."

if exemples and st.button(" Charger un texte du dataset"):
    st.session_state.texte = random.choice(exemples)[0]

texte = st.text_area("Texte à analyser", key="texte", height=220)

# Lancer l'extraction
if st.button("Extraire", type="primary"):
    try:
        rep = requests.post(
            API_URL,
            json={"texte": texte, "strategie": strategie, "temperature": temperature},
            timeout=300,
        )
        if rep.status_code != 200:
            st.error(f"Erreur {rep.status_code} : {rep.json().get('detail')}")
        else:
            donnees = rep.json()
            res = donnees["resultat"]
            st.success("JSON valide ✅")
            st.subheader(f"Relations ({len(res['relations'])})")
            st.table(res["relations"])
            if donnees["relations_ignorees"]:
                st.warning(f"{len(donnees['relations_ignorees'])} relation(s) hors liste retirée(s) par la validation")
                with st.expander("Voir les relations retirées"):
                    st.table(donnees["relations_ignorees"])
            st.subheader("Entités")
            st.table(res["entities"])
            with st.expander("JSON brut"):
                st.json(res)
    except requests.RequestException as e:
        st.error(f"Backend injoignable : {e}")
