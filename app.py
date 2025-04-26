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

# --- Session state defaults ---
if "page" not in st.session_state:
    st.session_state.page = "home"
if "coords" not in st.session_state:
    st.session_state.coords = None
if "selected_coords" not in st.session_state:
    st.session_state.selected_coords = None
if "selected_name" not in st.session_state:
    st.session_state.selected_name = None
if "show_map" not in st.session_state:
    st.session_state.show_map = False
if "mistral_calls" not in st.session_state:
    st.session_state.mistral_calls = []

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if st.session_state.page=="home" else "") + "🌿 Nouvelle identification"):
        st.session_state.page = "home"
    if st.button(("✅ " if st.session_state.page=="archives" else "") + "📚 Archives"):
        st.session_state.page = "archives"

# --- Archives page ---
if st.session_state.page == "archives":
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par :", ["Nom", "Date"])
    archives_sorted = sorted(archives, key=lambda x: x["nom"] if tri=="Nom" else x["date"])

    for i, plant in enumerate(archives_sorted):
        with st.expander(f"{plant['nom']} ({plant['date'][:10]})"):
            st.write(f"📅 Date : {plant['date']}")
            col1, col2, col3 = st.columns(3)
            if col1.button("📍 Localiser", key=f"loc_{i}"):
                st.session_state.selected_coords = plant.get("coords")
                st.session_state.selected_name = plant["nom"]
                st.session_state.show_map = True
            if col2.button("🔍 Vertus", key=f"virt_{i}"):
                st.markdown(f"### 🌿 Vertus de **{plant['nom']}**")
                st.write(plant.get("vertus", "Pas de vertus enregistrées"))
            if col3.button("❌ Supprimer", key=f"del_{i}"):
                archives.remove(plant)
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.experimental_rerun()
            new_name = st.text_input("✏️ Renommer :", plant["nom"], key=f"rn_{i}")
            if st.button("💾 Enregistrer nom", key=f"sv_{i}"):
                plant["nom"] = new_name
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.success("✅ Nom enregistré !")

    if st.session_state.show_map:
        st.markdown("---")
        st.markdown(f"### 🗺️ Localisation de : {st.session_state.selected_name}")
        pts = [
            {"lat": float(p["coords"].split(",")[0]), "lon": float(p["coords"].split(",")[1]), "name": p["nom"]}
            for p in archives if p.get("coords")
        ]
        if pts:
            df = pd.DataFrame(pts)
            st.map(df)
            sel = next(p for p in pts if p["name"]==st.session_state.selected_name)
            link = f"https://www.google.com/maps/dir/?api=1&destination={sel['lat']},{sel['lon']}"
            st.markdown(f"[🧭 Démarrer la navigation]({link})")
        if st.button("🔙 Retour liste"):
            st.session_state.show_map = False

    st.stop()

# --- Identification page ---
if st.session_state.page == "home":
    st.title("📷🌿 Identifier une plante")

    uploaded_file = st.file_uploader("Choisir ou prendre une photo", type=["jpg","jpeg","png"])
    if uploaded_file:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, use_container_width=True)

        # PlantNet identification
        try:
            with st.spinner("🔍 Identification PlantNet..."):
                resp = requests.post(
                    f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                    files={"images": (uploaded_file.name, io.BytesIO(image_bytes), mimetypes.guess_type(uploaded_file.name)[0] or "image/jpeg")},
                    data={"organs":"leaf"},
                    timeout=10
                )
                resp.raise_for_status()
                data_net = resp.json()
                if not data_net.get("results"):
                    raise ValueError()
            st.success("✅ PlantNet :")
            top = data_net["results"][:3]
            for r in top:
                sci = r["species"]["scientificNameWithoutAuthor"]
                score = round(r["score"]*100,1)
                st.write(f"- {sci} ({score}%)")
            plant_name = top[0]["species"]["scientificNameWithoutAuthor"]
        except Exception:
            st.warning("⚠️ PlantNet a échoué, essai Plant.id...")
            try:
                with st.spinner("🔍 Identification Plant.id..."):
                    hdr={"Api-Key":PLANTID_API_KEY}
                    resp2 = requests.post("https://api.plant.id/v2/identify", headers=hdr, files={"images":image_bytes}, timeout=15)
                    resp2.raise_for_status()
                    pid=resp2.json()
                    sug=pid["suggestions"][0]
                    plant_name=sug["plant_name"]
                    st.success(f"✅ Plant.id : {plant_name} ({round(sug['probability']*100,1)}%)")
            except Exception as e:
                st.error("❌ Échec identification")
                st.stop()

        st.session_state.plant_name = plant_name

        # Mistral virtues
        if plant_name in cache:
            virtues = cache[plant_name]
        else:
            now = datetime.utcnow()
            st.session_state.mistral_calls = [t for t in st.session_state.mistral_calls if now-t<timedelta(seconds=60)]
            if len(st.session_state.mistral_calls)<3:
                prompt = f"Nom courant {plant_name}. Comestible? Vertus médicinales? Usage?"
                hdr={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
                body={"model":"mistral-tiny","messages":[{"role":"user","content":prompt}],"max_tokens":200}
                res = requests.post("https://api.mistral.ai/v1/chat/completions",headers=hdr,json=body,timeout=15).json()
                virtues=res["choices"][0]["message"]["content"].strip()
                cache[plant_name]=virtues
                with open(CACHE_PATH,"w",encoding="utf-8") as f: json.dump(cache,f,ensure_ascii=False,indent=2)
            else:
                st.warning("🚦 Limite Mistral atteinte")
                virtues="(pas de vertus)"
        st.markdown(f"### 🌿 Vertus de **{plant_name}**")
        st.write(virtues)

        # Archiver au clic
        if st.button("✅ Archiver cette plante"):
            # Récupérer GPS
            gps = None
            try:
                gps = st.experimental_get_query_params().get("latlon",[None])[0]
            except: pass
            archives.append({"nom":plant_name,"date":datetime.now().isoformat(),"coords":gps,"vertus":virtues})
            with open(ARCHIVES_PATH,"w",encoding="utf-8") as f: json.dump(archives,f,ensure_ascii=False,indent=2)
            st.success("🌱 Plante archivée !")













