import streamlit as st
import requests
import os
import io
import json
import mimetypes
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image

# --- Charger les clés depuis .env ---
load_dotenv()
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
PLANTID_API_KEY = os.getenv("PLANTID_API_KEY")  # Clé API Plant.id

# --- Chemin du fichier de cache ---
CACHE_PATH = "cache_virtues.json"

# --- Charger ou initialiser le cache ---
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# --- Initialiser le suivi des appels Mistral dans session_state ---
if 'mistral_calls' not in st.session_state:
    st.session_state.mistral_calls = []
if 'retry_after' not in st.session_state:
    st.session_state.retry_after = None

# --- Interface Streamlit ---
st.set_page_config(page_title="Plante + Vertus", layout="centered")
st.title("📷🌿 Identification de plante + vertus")

uploaded_file = st.file_uploader("Choisir ou prendre une photo", type=["jpg","jpeg","png"])
if not uploaded_file:
    st.info("En attente d'une photo...")
    st.stop()

# Lire et afficher l’image
image_bytes = uploaded_file.read()
image = Image.open(io.BytesIO(image_bytes))
st.image(image, caption="Image sélectionnée", use_container_width=True)

# --- Appel PlantNet ---
use_plantnet = True
try:
    with st.spinner("🔍 Identification en cours..."):
        url = f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}"
        mime_type = mimetypes.guess_type(uploaded_file.name)[0] or "image/jpeg"
        files = {"images": (uploaded_file.name, io.BytesIO(image_bytes), mime_type)}
        data = {"organs": "leaf"}
        resp = requests.post(url, files=files, data=data)
        resp.raise_for_status()

        data_net = resp.json()
        if not data_net.get("results"):
            raise ValueError("Aucun résultat PlantNet")
except Exception as err:
    st.warning(f"⚠️ PlantNet indisponible : {err}\n–> Bascule sur Plant.id")
    use_plantnet = False

if use_plantnet:
    first = data_net["results"][0]
    plant_name = first["species"]["scientificNameWithoutAuthor"]
    common_names = first["species"].get("commonNames", [])
    common_name_display = f" ({common_names[0]})" if common_names else ""
    prob1 = round(first["score"] * 100, 1)
    st.success(f"✅ Plante identifiée : **{plant_name}**{common_name_display} ({prob1}%)")
else:
    # --- Appel Plant.id ---
    plantid_key = os.getenv("PLANTID_API_KEY")
    files2 = {"images": image_bytes}
    headers2 = {"Api-Key": plantid_key}
    resp2 = requests.post(
        "https://api.plant.id/v2/identify",
        files=files2,
        headers=headers2,
        timeout=15
    )
    resp2.raise_for_status()
    pid = resp2.json()
    suggestion = pid["suggestions"][0]
    plant_name = suggestion["plant_name"]
    score = round(suggestion["probability"]*100,1)
    st.success(f"✅ Plant.id : {plant_name} ({score}%)")

# Info GPS désactivée sur Streamlit Cloud
st.info("📍 Marquage GPS non disponible sur la version en ligne de Streamlit. Fonction active uniquement en version locale ou mobile.")

# --- Vérifier le cache ---
if plant_name in cache:
    st.markdown(f"### 🌿 Vertus de **{plant_name}** (depuis le cache)")
    st.write(cache[plant_name])
    st.stop()

# --- Gestion rate limit et retry ---
now = datetime.utcnow()
st.session_state.mistral_calls = [ts for ts in st.session_state.mistral_calls if now - ts < timedelta(seconds=60)]

if st.session_state.retry_after:
    wait = int((st.session_state.retry_after - now).total_seconds())
    if wait > 0:
        placeholder = st.empty()
        if 'start_timer' not in st.session_state:
            st.session_state.start_timer = datetime.utcnow()
        elapsed = int((datetime.utcnow() - st.session_state.start_timer).total_seconds())
        countdown = max(wait - elapsed, 0)
        placeholder.warning(f"🚦 Nouvelle requête possible dans {countdown} secondes...")
        if countdown == 0 and st.button("Relancer l'appel Mistral"):
            st.session_state.retry_after = None
            st.session_state.start_timer = None
            st.experimental_rerun()
        st.stop()
    else:
        st.session_state.retry_after = None

if len(st.session_state.mistral_calls) >= 3:
    oldest = st.session_state.mistral_calls[0]
    st.session_state.retry_after = oldest + timedelta(seconds=60)
    st.session_state.start_timer = datetime.utcnow()
    st.experimental_rerun()

# --- Appel Mistral et mise en cache ---
prompt = f"Cette plante est-elle comestible ? Quelles sont ses vertus médicinales et comment l'utiliser ? Réponds pour : {plant_name}."
st.text(f"🔎 Prompt : {prompt}")

headers = {
    "Authorization": f"Bearer {MISTRAL_API_KEY}",
    "Content-Type": "application/json",
}
json_data = {
    "model": "mistral-tiny",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.7,
    "max_tokens": 400,
}

try:
    st.session_state.mistral_calls.append(now)
    response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=json_data)
    response.raise_for_status()
    result = response.json()
    answer = result["choices"][0]["message"]["content"].strip()

    st.markdown(f"### 🌿 Vertus de **{plant_name}**")
    st.write(answer)
    cache[plant_name] = answer
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

except Exception as e:
    st.error("❌ Erreur lors de l’appel à Mistral.")
    st.exception(e)

