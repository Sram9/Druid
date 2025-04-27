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

# --- Initialisation session_state ---
state = st.session_state
if "page" not in state:
    state.page = "home"
if "coords" not in state:
    state.coords = None
if "selected_coords" not in state:
    state.selected_coords = None
if "selected_name" not in state:
    state.selected_name = None
if "show_map" not in state:
    state.show_map = False
if "mistral_calls" not in state:
    state.mistral_calls = []

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if state.page == "home" else "") + "🌿 Nouvelle identification"):
        state.page = "home"
    if st.button(("✅ " if state.page == "archives" else "") + "📚 Archives"):
        state.page = "archives"
    if st.button(("✅ " if state.page == "search" else "") + "🔍 Recherche par propriétés"):
        state.page = "search"

# --- Recherche par propriétés ---
if state.page == "search":
    st.title("🔍 Recherche par propriétés")
    term = st.text_input("🔎 Mot-clé dans vertus")
    if term:
        results = [p for p in archives if term.lower() in p.get("vertus", "").lower()]
        if results:
            for plant in results:
                st.write(f"🌿 **{plant['nom']}** — {plant['date'][:10]}")
                st.write(plant.get("vertus", "Aucune information"))
                st.markdown("---")
        else:
            st.info("Aucune plante trouvée pour ce mot-clé.")
    else:
        st.write("Entrez un mot-clé pour lancer la recherche.")
    st.stop()

# --- Archives page ---
if state.page == "archives":
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par :", ["Nom", "Date"])
    sorted_archives = sorted(archives, key=lambda x: x["nom"] if tri == "Nom" else x["date"], reverse=False)
    for i, plant in enumerate(sorted_archives):
        with st.expander(f"{plant['nom']} ({plant['date'][:10]})"):
            st.write(f"📅 Date : {plant['date']}")
            col1, col2, col3 = st.columns(3)
            if col1.button("📍 Localiser", key=f"loc_{i}"):
                state.selected_coords = plant.get("coords")
                state.selected_name = plant["nom"]
                state.show_map = True
            if col2.button("🔍 Vertus", key=f"virt_{i}"):
                st.write(plant.get("vertus", "Pas de vertus enregistrées"))
            if col3.button("❌ Supprimer", key=f"del_{i}"):
                archives.remove(plant)
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.experimental_rerun()
            new_name = st.text_input("✏️ Renommer :", plant['nom'], key=f"rn_{i}")
            if st.button("💾 Enregistrer nom", key=f"sv_{i}"):
                plant['nom'] = new_name
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.success("Nom mis à jour !")
    if state.show_map:
        st.markdown("---")
        st.title(f"🗺️ {state.selected_name}")
        points = []
        for p in archives:
            if p.get("coords"):
                lat, lon = map(float, p["coords"].split(","))
                points.append({"lat": lat, "lon": lon})
        if points:
            df = pd.DataFrame(points)
            st.map(df)
        if st.button("🔙 Retour"):
            state.show_map = False
    st.stop()

# --- Home page: identification ---
st.title("📷🌿 Identification de plante + vertus")
uploaded_file = st.file_uploader("Choisir ou prendre une photo", type=["jpg","jpeg","png"])
if uploaded_file:
    image_bytes = uploaded_file.read()
    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, use_container_width=True)
    # Identification PlantNet
    try:
        with st.spinner("🔍 PlantNet..."):
            resp = requests.post(
                f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                files={"images": (uploaded_file.name, io.BytesIO(image_bytes), mimetypes.guess_type(uploaded_file.name)[0] or "image/jpeg")},
                data={"organs":"leaf"}, timeout=10)
            resp.raise_for_status()
            data_net = resp.json()
            if not data_net.get("results"): raise ValueError()
        st.success("✅ PlantNet:")
        top = data_net["results"][0]
        plant_name = top["species"]["scientificNameWithoutAuthor"]
    except:
        st.warning("PlantNet failed, using Plant.id...")
        try:
            with st.spinner("🔍 Plant.id..."):
                hdr={"Api-Key":PLANTID_API_KEY}
                r2 = requests.post("https://api.plant.id/v2/identify", headers=hdr, files={"images":image_bytes}, timeout=15)
                r2.raise_for_status()
                pid=r2.json()["suggestions"][0]
                plant_name = pid["plant_name"]
        except:
            st.error("Identification failed")
            st.stop()
    state.plant_name = plant_name
    # Vertus Mistral
    if plant_name in cache:
        virtues = cache[plant_name]
    else:
        now = datetime.utcnow()
        state.mistral_calls = [t for t in state.mistral_calls if now - t < timedelta(seconds=60)]
        if len(state.mistral_calls) < 3:
            prompt = f"Nom courant {plant_name}. Comestible? Vertus médicinales?"
            hdr={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
            body={"model":"mistral-tiny","messages":[{"role":"user","content":prompt}],"max_tokens":200}
            res=requests.post("https://api.mistral.ai/v1/chat/completions",headers=hdr,json=body,timeout=15).json()
            virtues=res["choices"][0]["message"]["content"].strip()
            cache[plant_name]=virtues
            with open(CACHE_PATH,"w",encoding="utf-8") as f: json.dump(cache,f,ensure_ascii=False,indent=2)
        else:
            virtues="(Limite atteinte)"
    st.markdown(f"### 🌿 Vertus de **{plant_name}**")
    st.write(virtues)
    if st.button("✅ Archiver cette plante"):
        # demander GPS
        js = """<script>navigator.geolocation.getCurrentPosition(p=>{let c=p.coords.latitude+','+p.coords.longitude;window.parent.postMessage({coords:c}, '*');});</script>"""
        st.components.v1.html(js)
        if 'coords' in state and state.coords:
            coord = state.coords
        else:
            coord = None
        archives.append({"nom":plant_name,"date":datetime.now().isoformat(),"coords":coord,"vertus":virtues})
        with open(ARCHIVES_PATH,"w",encoding="utf-8") as f: json.dump(archives,f,ensure_ascii=False,indent=2)
        st.success("Plante archivée !")
'''
















