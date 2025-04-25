import streamlit as st
import requests
import os
import io
import json
import mimetypes
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image

# --- Initialisation de la page Streamlit (doit être la première commande) ---
st.set_page_config(page_title="Plante + Vertus", layout="centered")

# --- Charger les clés depuis .env ---
load_dotenv()
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY")
PLANTID_API_KEY = os.getenv("PLANTID_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# --- Chemin du fichier de cache ---
CACHE_PATH = "cache_virtues.json"

# --- Charger ou initialiser le cache ---
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# --- Suivi des appels Mistral dans session_state ---
if 'mistral_calls' not in st.session_state:
    st.session_state.mistral_calls = []
if 'retry_after' not in st.session_state:
    st.session_state.retry_after = None

# --- Interface utilisateur ---
st.title("📷🌿 Identification de plante + vertus")

uploaded_file = st.file_uploader("Choisir ou prendre une photo", type=["jpg","jpeg","png"])
if uploaded_file:
    # Lire et afficher l’image
    image_bytes = uploaded_file.read()
    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, caption="Image sélectionnée", use_container_width=True)

    # --- Tentative d'identification avec PlantNet (timeout 10s) ---
    use_plantnet = True
    try:
        with st.spinner("🔍 Identification PlantNet en cours..."):
            url = f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}"
            mime_type = mimetypes.guess_type(uploaded_file.name)[0] or "image/jpeg"
            files = {"images": (uploaded_file.name, io.BytesIO(image_bytes), mime_type)}
            data = {"organs": "leaf"}
            resp = requests.post(url, files=files, data=data, timeout=10)
            resp.raise_for_status()
            data_net = resp.json()
            if not data_net.get("results"):
                raise ValueError("Aucun résultat PlantNet")
    except Exception as err:
        st.warning(f"⚠️ PlantNet indisponible ou timeout : {err}\n–> Bascule sur Plant.id")
        use_plantnet = False

    # --- Traitement des résultats PlantNet ---
    if use_plantnet:
        st.success("✅ Résultats PlantNet :")
        top3 = data_net["results"][:3]
        if "plant_name" not in st.session_state and top3:
            st.session_state.plant_name = top3[0]["species"].get("scientificNameWithoutAuthor", "?")

        for idx, result in enumerate(top3, 1):
            sci_name = result["species"].get("scientificNameWithoutAuthor", "?")
            common_names = result["species"].get("commonNames", [])
            common_name = common_names[0] if common_names else "(nom courant inconnu)"
            prob = round(result["score"] * 100, 1)
            button_label = f"{idx}. {sci_name} — {common_name} ({prob}%)"
            if st.button(button_label):
                st.session_state.plant_name = sci_name
    else:
        # Identification via Plant.id
        with st.spinner("🔍 Identification Plant.id en cours..."):
            headers = {"Api-Key": PLANTID_API_KEY}
            files2 = {"images": image_bytes}
            resp2 = requests.post(
                "https://api.plant.id/v2/identify",
                headers=headers,
                files=files2,
                timeout=15
            )
            resp2.raise_for_status()
            pid = resp2.json()
            suggestion = pid.get("suggestions", [])[0]
            plant_name = suggestion.get("plant_name", "Inconnu")
            score = round(suggestion.get("probability", 0) * 100, 1)
            st.success(f"✅ Plant.id : **{plant_name}** ({score}%)")
            st.session_state.plant_name = plant_name

# --- Suite si une plante est définie ---
plant_name = st.session_state.get("plant_name")
if not plant_name:
    st.stop()

# Info GPS désactivée
st.info("📍 Marquage GPS non disponible sur le web. Utilisable en local/mobile.")

# --- Vérifier le cache pour les vertus ---
if plant_name in cache:
    st.markdown(f"### 🌿 Vertus de **{plant_name}** (cache)")
    st.write(cache[plant_name])
    st.stop()

# --- Gestion rate limit pour Mistral ---
now = datetime.utcnow()
st.session_state.mistral_calls = [ts for ts in st.session_state.mistral_calls if now - ts < timedelta(seconds=60)]
if len(st.session_state.mistral_calls) >= 3:
    st.error("🚦 Limite de 3 requêtes Mistral/min atteinte. Rafraîchis dans un instant.")
    st.stop()

# --- Appel Mistral pour les vertus ---
prompt = f"Quel est le nom courant de cette plante ? Cette plante est-elle comestible ? Quelles sont ses vertus médicinales et comment l'utiliser ? Réponds pour : {plant_name}."
st.text(f"🔎 Prompt : {prompt}")
headers_m = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
json_data = {"model": "mistral-tiny", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400}

try:
    st.session_state.mistral_calls.append(now)
    resp_m = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers_m, json=json_data, timeout=15)
    resp_m.raise_for_status()
    result_m = resp_m.json()
    answer = result_m["choices"][0]["message"]["content"].strip()
    st.markdown(f"### 🌿 Vertus de **{plant_name}**")
    st.write(answer)
    cache[plant_name] = answer
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
except Exception as e:
    st.error("❌ Erreur lors de l’appel à Mistral.")
    st.text(str(e))




