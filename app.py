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

# --- Fichiers de stockage ---
CACHE_PATH = "cache_virtues.json"
ARCHIVES_PATH = "archives.json"

# --- Charger ou initialiser cache et archives ---
cache = json.load(open(CACHE_PATH, "r", encoding="utf-8")) if os.path.exists(CACHE_PATH) else {}
archives = json.load(open(ARCHIVES_PATH, "r", encoding="utf-8")) if os.path.exists(ARCHIVES_PATH) else []

# --- Session state defaults ---
state = st.session_state
if 'page' not in state: state.page = 'home'
if 'coords' not in state: state.coords = ""
if 'selected_coords' not in state: state.selected_coords = ""
if 'selected_name' not in state: state.selected_name = ""
if 'show_map' not in state: state.show_map = False
if 'mistral_calls' not in state: state.mistral_calls = []

# --- Hidden input to hold coords ---
# This text_input is hidden but keeps session_state.coords in sync
_ = st.text_input("coords", value=state.coords, key="coords", label_visibility="collapsed")

# --- JS to request GPS once on load ---
gps_request = """
<script>
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const c = pos.coords.latitude + "," + pos.coords.longitude;
      const input = window.parent.document.querySelector('input[data-testid="coords"]');
      if (input) {
        input.value = c;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    },
    (err) => {
      console.warn("GPS error:", err);
    }
  );
}
</script>
"""
st.components.v1.html(gps_request)

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if state.page=='home' else "") + "🌿 Nouvelle identification"):
        state.page = 'home'
    if st.button(("✅ " if state.page=='archives' else "") + "📚 Archives"):
        state.page = 'archives'

# --- Archives page ---
if state.page == 'archives':
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom","Date"])
    sorted_archives = sorted(archives, key=lambda p: p['nom'] if order=="Nom" else p['date'])
    for i,p in enumerate(sorted_archives):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1,c2,c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                state.selected_coords, state.selected_name, state.show_map = p.get('coords'), p['nom'], True
            if c2.button("🔍 Vertus", key=f"v{i}"):
                st.write(p.get('vertus',"Aucune vertu"))
            if c3.button("❌ Supprimer", key=f"d{i}"):
                archives.remove(p)
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.experimental_rerun()
            new = st.text_input("✏️ Renommer :", value=p['nom'], key=f"rn{i}")
            if st.button("💾 Enregistrer nom", key=f"sv{i}"):
                p['nom']=new
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Nom mis à jour")
    if state.show_map:
        if state.selected_coords:
            lat,lon = state.selected_coords.split(",")
            df = pd.DataFrame([{"lat":float(lat),"lon":float(lon)}])
            st.map(df)
        else:
            st.error("⚠️ Pas de coordonnées GPS.")
        if st.button("🔙 Retour archives"):
            state.show_map=False
    st.stop()

# --- Identification page ---
st.title("📷🌿 Identifier une plante")
up = st.file_uploader("Photo", type=["jpg","jpeg","png"])
if up:
    img_bytes=up.read()
    st.image(Image.open(io.BytesIO(img_bytes)),use_container_width=True)
    # PlantNet
    try:
        r=requests.post(
            f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
            files={"images":(up.name,io.BytesIO(img_bytes),mimetypes.guess_type(up.name)[0]or"image/jpeg")},
            data={"organs":"leaf"},timeout=10
        )
        r.raise_for_status()
        res=r.json()["results"]
        sug=res[:3]
        st.write([f"{s['species']['scientificNameWithoutAuthor']} ({s['score']*100:.1f}%)" for s in sug])
        name=sug[0]['species']['scientificNameWithoutAuthor']
    except:
        st.warning("PlantNet failed, use Plant.id")
        j=requests.post("https://api.plant.id/v2/identify",headers={"Api-Key":PLANTID_API_KEY},files={"images":img_bytes}).json()
        s=j["suggestions"][0]; name=s["plant_name"]
        st.write(f"{name} ({s['probability']*100:.1f}%)")
    state.plant_name=name
    # Mistral
    if name in cache:
        v=cache[name]
    else:
        now=datetime.utcnow()
        state.mistral_calls=[t for t in state.mistral_calls if now-t<timedelta(60)]
        if len(state.mistral_calls)<3:
            body={"model":"mistral-tiny","messages":[{"role":"user","content":f"Nom courant {name}, comestible, vertus médicinales?"}], "max_tokens":200}
            h={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
            j=requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=body).json()
            v=j["choices"][0]["message"]["content"]; cache[name]=v; open(CACHE_PATH,'w').write(json.dumps(cache,ensure_ascii=False,indent=2))
            state.mistral_calls.append(now)
        else:
            v="Limite Mistral"
    st.write(v)
    # Archiver
    if st.button("✅ Archiver cette plante"):
        archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":state.coords,"vertus":v})
        open(ARCHIVES_PATH,'w').write(json.dumps(archives,ensure_ascii=False,indent=2))
        st.success("Archivée !")






















