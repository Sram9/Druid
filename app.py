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

# --- Initialiser session state ---
state = st.session_state
if 'page' not in state: state.page = 'home'
if 'coords' not in state: state.coords = None
if 'selected_coords' not in state: state.selected_coords = None
if 'selected_name' not in state: state.selected_name = None
if 'show_map' not in state: state.show_map = False
if 'mistral_calls' not in state: state.mistral_calls = []

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
    order = st.radio("Trier par :", ["Nom", "Date"])
    sorted_archives = sorted(archives, key=lambda p: p['nom'] if order=='Nom' else p['date'])
    for i,p in enumerate(sorted_archives):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1,c2,c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                state.selected_coords, state.selected_name, state.show_map = p.get('coords'), p['nom'], True
            if c2.button("🔍 Vertus", key=f"virt{i}"):
                st.write(p.get('vertus','Aucune vertu enregistrée'))
            if c3.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.experimental_rerun()
            new = st.text_input("✏️ Renommer :", value=p['nom'], key=f"rn{i}")
            if st.button("💾 Enregistrer nom", key=f"sv{i}"):
                p['nom']=new
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Nom mis à jour")
    if state.show_map:
        st.map(pd.DataFrame([{'lat':float(state.selected_coords.split(',')[0]), 'lon':float(state.selected_coords.split(',')[1])}]))
        if st.button("🔙 Retour archives"): state.show_map=False
    st.stop()

# --- Identification page ---
state.page='home'
st.title("📷🌿 Identifier une plante")
up = st.file_uploader("Photo", type=["jpg","jpeg","png"])
if up:
    img_bytes=up.read(); st.image(Image.open(io.BytesIO(img_bytes)),use_container_width=True)
    # PlantNet
    try:
        r=requests.post(f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}", files={"images":(up.name,io.BytesIO(img_bytes),mimetypes.guess_type(up.name)[0]or'')}, data={"organs":"leaf"}, timeout=10)
        r.raise_for_status(); res=r.json()['results']
        suggestions=res[:3]; name=suggestions[0]['species']['scientificNameWithoutAuthor']
        st.write([f"{s['species']['scientificNameWithoutAuthor']} ({s['score']*100:.1f}%)" for s in suggestions])
    except:
        st.warning("PlantNet failed, using Plant.id")
        j=requests.post("https://api.plant.id/v2/identify",headers={"Api-Key":PLANTID_API_KEY},files={"images":img_bytes}).json()
        sug=j['suggestions'][0]; name=sug['plant_name']; st.write(f"{name} ({sug['probability']*100:.1f}%)")
    state.plant_name=name
    # Mistral
    if name in cache: v=cache[name]
    else:
        state.mistral_calls=[t for t in state.mistral_calls if datetime.utcnow()-t<timedelta(seconds=60)]
        if len(state.mistral_calls)<3:
            body={"model":"mistral-tiny","messages":[{"role":"user","content":f"Nom courant {name}, comestible et vertus?"}],"max_tokens":200}
            h={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
            j=requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=body).json()
            v=j['choices'][0]['message']['content']; cache[name]=v; open(CACHE_PATH,'w',encoding='utf-8').write(json.dumps(cache,ensure_ascii=False,indent=2))
            state.mistral_calls.append(datetime.utcnow())
        else: v="Limite atteinte"
    st.write(v)
    # Archiver
    if st.button("✅ Archiver cette plante"):
        # get GPS
        gps_script="""<script>navigator.geolocation.getCurrentPosition(p=>{const c=p.coords.latitude+','+p.coords.longitude;const i=window.parent.document.querySelector('input[data-testid="stSessionState.coords"]');if(i){i.value=c;i.dispatchEvent(new Event('input',{bubbles:true}));}});</script>"""
        st.components.v1.html(gps_script)
        archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":state.coords,"vertus":v})
        open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
        st.success("Archiv&eacute;!")




















