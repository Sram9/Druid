import streamlit as st
import requests
import os
import io
import json
import mimetypes
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image
import pandas as pd

# --- Initialisation de la page Streamlit ---
st.set_page_config(page_title="Plante + Vertus", layout="centered")

# --- Charger les clés depuis .env ---
load_dotenv()
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY")
PLANTID_API_KEY = os.getenv("PLANTID_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# --- Chemins des fichiers ---
CACHE_PATH = "cache_virtues.json"
ARCHIVES_PATH = "archives.json"

# --- Charger ou initialiser le cache ---
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# --- Charger ou initialiser les archives ---
if os.path.exists(ARCHIVES_PATH):
    with open(ARCHIVES_PATH, "r", encoding="utf-8") as f:
        archives = json.load(f)
else:
    archives = []

# --- Suivi des appels Mistral dans session_state ---
if 'mistral_calls' not in st.session_state:
    st.session_state.mistral_calls = []
if 'retry_after' not in st.session_state:
    st.session_state.retry_after = None
if 'coords' not in st.session_state:
    st.session_state.coords = None

# --- MENU ACCESSIBLE EN HAUT A DROITE ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button("🌿 Nouvelle identification"):
        st.session_state.page = "home"
        st.experimental_rerun()
    if st.button("📚 Voir mes plantes archivées"):
        st.session_state.page = "archives"
        st.experimental_rerun()

if st.session_state.get("page") == "archives":
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par :", ["Nom", "Date"])
    archives_sorted = sorted(archives, key=lambda x: x["nom" if tri == "Nom" else "date"])

    for i, plant in enumerate(archives_sorted):
        with st.expander(f"{plant['nom']} ({plant['date'][:10]})"):
            st.write(f"📅 Date : {plant['date']}")
            if st.button(f"📍 Localiser sur une carte", key=f"map_{i}"):
                st.session_state.selected_coords = plant.get("coords")
                st.session_state.selected_name = plant["nom"]
                st.session_state.show_map = True
                st.experimental_rerun()
            if st.button(f"❌ Supprimer", key=f"del_{i}"):
                archives.remove(plant)
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.success("Plante supprimée.")
                st.experimental_rerun()
            new_name = st.text_input("✏️ Renommer la plante :", value=plant["nom"], key=f"rename_{i}")
            if st.button("💾 Enregistrer le nouveau nom", key=f"save_{i}"):
                plant["nom"] = new_name
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.success("✅ Nom enregistré !")
                st.experimental_rerun()

    if "show_map" in st.session_state and st.session_state.show_map:
        st.markdown("---")
        st.markdown(f"### 🗺️ Localisation de : {st.session_state.selected_name}")
        points = [
            {"lat": float(p["coords"].split(",")[0]), "lon": float(p["coords"].split(",")[1]), "name": p["nom"]}
            for p in archives if p.get("coords")
        ]
        if points:
            df = pd.DataFrame(points)
            st.map(df)
            selected = next((p for p in points if p['name'] == st.session_state.selected_name), points[0])
            maps_link = f"https://www.google.com/maps/dir/?api=1&destination={selected['lat']},{selected['lon']}"
            st.markdown(f"[🧭 Démarrer la navigation]({maps_link})", unsafe_allow_html=True)
        if st.button("🔙 Retour à la liste"):
            st.session_state.show_map = False
            st.experimental_rerun()
    st.stop()

# --- Sinon : Identification d'une nouvelle plante ---
if st.session_state.get("page") != "archives":
    st.session_state.page = "home"

st.title("📷🌿 Identification de plante + vertus")

uploaded_file = st.file_uploader("Choisir ou prendre une photo", type=["jpg", "jpeg", "png"])
if uploaded_file:
    image_bytes = uploaded_file.read()
    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, caption="Image sélectionnée", use_container_width=True)

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
        with st.spinner("🔍 Identification Plant.id en cours..."):
            headers = {"Api-Key": PLANTID_API_KEY}
            files2 = {"images": image_bytes}
            resp2 = requests.post("https://api.plant.id/v2/identify", headers=headers, files=files2, timeout=15)
            resp2.raise_for_status()
            pid = resp2.json()
            suggestion = pid.get("suggestions", [])[0]
            plant_name = suggestion.get("plant_name", "Inconnu")
            score = round(suggestion.get("probability", 0) * 100, 1)
            st.success(f"✅ Plant.id : **{plant_name}** ({score}%)")
            st.session_state.plant_name = plant_name

plant_name = st.session_state.get("plant_name")
if not plant_name:
    st.stop()

st.markdown("---")

# --- Afficher les vertus directement après identification ---
if plant_name in cache:
    st.markdown(f"### 🌿 Vertus de **{plant_name}** (cache)")
    st.write(cache[plant_name])
else:
    now = datetime.utcnow()
    st.session_state.mistral_calls = [ts for ts in st.session_state.mistral_calls if now - ts < timedelta(seconds=60)]
    if len(st.session_state.mistral_calls) < 3:
        prompt = f"Quel est le nom courant de cette plante ? Cette plante est-elle comestible ? Quelles sont ses vertus médicinales et comment l'utiliser ? Réponds pour : {plant_name}."
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
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ Erreur avec Mistral: {e}")
    else:
        st.warning("⚠️ Trop d'appels à l'API Mistral. Veuillez patienter.")












