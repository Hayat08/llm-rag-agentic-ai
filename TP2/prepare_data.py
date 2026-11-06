
import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

# Colonnes utiles 
CANDIDATS_TEXTE = ["text", "full_text", "texte", "content", "contenu"]
CHAMPS_META = ["jurisdiction", "chamber", "decision_date", "number", "ecli",
               "solution", "formation", "publication"]

parser = argparse.ArgumentParser()
parser.add_argument("--n", type=int, default=2000, help="nombre de décisions gardées")
parser.add_argument("--court", default="cour_de_cassation",
                    help="cour_de_cassation, cour_d_appel ou tribunal_judiciaire (783 Mo, le plus léger)")
parser.add_argument("--local", default=None, help="chemin d'un fichier .parquet déjà téléchargé")
parser.add_argument("--premieres", action="store_true",
                    help="prend simplement les N premières décisions du fichier (rapide, mais très anciennes)")
args = parser.parse_args()

#  Obtenir le fichier parquet en local 
if args.local:
    chemin = args.local
else:
    from huggingface_hub import hf_hub_download
    print(f"Téléchargement de {args.court}.parquet (barre de progression ci-dessous, reprise possible)...")
    chemin = hf_hub_download(repo_id="antoinejeannot/jurisprudence", filename=f"{args.court}.parquet",
                             repo_type="dataset")
print("Fichier :", chemin)

#  Lecture progressive 
fichier = pq.ParquetFile(chemin, buffer_size=1 << 20)     # lit par petits morceaux (1 Mo)
noms = fichier.schema_arrow.names
print("Colonnes du fichier :", noms)
print(f"{fichier.metadata.num_rows} décisions au total, {fichier.metadata.num_row_groups} blocs")

colonne_texte = next((c for c in CANDIDATS_TEXTE if c in noms), None)
print("Colonne de texte utilisée :", colonne_texte)
if colonne_texte is None:
    raise SystemExit("ERREUR : colonne du texte introuvable. Ajoute son nom dans CANDIDATS_TEXTE "
                     "(voir 'Colonnes du fichier' ci-dessus).")

voulues = [c for c in ["id", colonne_texte] + CHAMPS_META if c in noms]   # on ignore les colonnes lourdes inutiles

#  Écriture de data/cases.jsonl 
MAX_CARACTERES = 30000      # on évite les décisions gigantesques (index trop lourd)
total = fichier.metadata.num_rows
pas = 1 if args.premieres else max(1, round(total / args.n))    # 1 décision gardée toutes les 'pas' lignes
print(f"Échantillonnage : 1 décision sur {pas}" if pas > 1 else "Échantillonnage : premières décisions")

Path("data").mkdir(exist_ok=True)
gardees, ligne = 0, -1
with open("data/cases.jsonl", "w", encoding="utf-8") as f:
    for bloc in fichier.iter_batches(batch_size=50, columns=voulues):
        for ex in bloc.to_pylist():
            ligne += 1
            if ligne % pas:                       # ligne non retenue par l'échantillonnage
                continue
            texte = ex.get(colonne_texte) or ""
            if not 1500 <= len(texte) <= MAX_CARACTERES:   # trop courte (vide) ou trop longue
                continue
            cas = {"id": str(ex.get("id")), "text": texte}
            for champ in CHAMPS_META:
                cas[champ] = ex.get(champ)
            f.write(json.dumps(cas, ensure_ascii=False, default=str) + "\n")
            gardees += 1
            if gardees >= args.n:
                break
        if ligne % 20000 < 50:
            print(f"  {ligne}/{total} lignes lues, {gardees} décisions gardées", flush=True)
        if gardees >= args.n:
            break

if gardees == 0:
    print("ERREUR : 0 décision gardée (textes trop courts ou colonne incorrecte).")
else:
    print(f"{gardees} décisions sauvegardées dans data/cases.jsonl")