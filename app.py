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

# --- Initialisation du cache et archives ---
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
        cache = {}
if os.path.exists(ARCHIVES_PATH):
    with open(ARCHIVES_PATH, "r", encoding="utf-8") as f:
        archives = json.load(f)
else:
        archives = []

# --- État de session ---
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'coords' not in st.session_state:
    st.session_state.coords = None
if 'mistral_calls' not in st.session_state:
    st.session_state.mistral_calls = []
if 'show_map' not in st.session_state:
    st.session_state.show_map = False

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button("🌿 Nouvelle identification"):
        st.session_state.page = 'home'
    if st.button("📚 Archives"):
        st.session_state.page = 'archives'
    if st.button("🔍 Recherche par propriétés"):
        st.session_state.page = 'search'

# --- Page recherche par propriétés ---
if st.session_state.page == 'search':
    st.title("🔍 Recherche par propriétés")
    term = st.text_input("Entrez un mot-clé :")
    if term:
        results = [p for p in archives if term.lower() in p.get('vertus','').lower()]
        for p in results:
            st.write(f"🌿 **{p['nom']}** ({p['date'][:10]})")
            st.write(p.get('vertus','Aucune info'))
    else:
        st.write("Aucun mot-clé saisi.")

# --- Page archives ---
if st.session_state.page == 'archives':
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par :", ["Nom","Date"])
    sorted_arch = sorted(archives, key=lambda x: x['nom'] if tri=='Nom' else x['date'])
    for i,p in enumerate(sorted_arch):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(p.get('vertus','(pas de vertus)'))
            cols = st.columns(3)
            if cols[0].button("📍 Localiser", key=f"loc{i}"):
                st.session_state.selected_coords = p.get('coords')
                st.session_state.show_map = True
            if cols[1].button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                with open(ARCHIVES_PATH,'w') as f: json.dump(archives,f,ensure_ascii=False,indent=2)
                st.experimental_rerun()
            new = cols[2].text_input("✏️ Renommer", value=p['nom'], key=f"rn{i}")
            if cols[2].button("💾", key=f"sv{i}"):
                p['nom']=new
                with open(ARCHIVES_PATH,'w') as f: json.dump(archives,f,ensure_ascii=False,indent=2)
                st.experimental_rerun()
    if st.session_state.show_map:
        df = pd.DataFrame([{ 'lat':float(c.split(',')[0]), 'lon':float(c.split(',')[1]) } for c in [pl.get('coords') for pl in archives if pl.get('coords')]])
        st.map(df)
    st.stop()

# --- Page identification ---
st.title("📷🌿 Identifier une plante")
file = st.file_uploader("Photo",type=["jpg","png"])
if file:
    img_bytes = file.read()
    st.image(Image.open(io.BytesIO(img_bytes)),use_container_width=True)
    # PlantNet
    try:
        res = requests.post(f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
            files={"images":(file.name,io.BytesIO(img_bytes),mimetypes.guess_type(file.name)[0] or 'image/jpeg')},
            data={"organs":"leaf"},timeout=10)
        res.raise_for_status()
        resj=res.json()['results'][:3]
        name=resj[0]['species']['scientificNameWithoutAuthor']
    except:
        name='Inconnu'
    st.session_state.plant_name=name
    st.write(f"**{name}**")
    # Mistral
    if name in cache: v=cache[name]
    else:
        prompt=f"Vertus {name}?"
        hdr={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
        body={"model":"mistral-tiny","messages":[{"role":"user","content":prompt}],"max_tokens":200}
        v=requests.post("https://api.mistral.ai/v1/chat/completions",headers=hdr,json=body).json()["choices"][0]["message"]["content"]
        cache[name]=v
        with open(CACHE_PATH,'w') as f: json.dump(cache,f,ensure_ascii=False,indent=2)
    st.write(v)
    if st.button("✅ Archiver"):
        coords=None
        gps_js="""<script>navigator.geolocation.getCurrentPosition(pos=>{let c=pos.coords.latitude+','+pos.coords.longitude;let inp=window.parent.document.querySelector('input[data-testid=\"stSessionState.coords\"]');if(inp){inp.value=c;inp.dispatchEvent(new Event('input',{bubbles:true}));}});</script>"""
        st.components.v1.html(gps_js)
        archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":st.session_state.coords,"vertus":v})
        with open(ARCHIVES_PATH,'w') as f: json.dump(archives,f,ensure_ascii=False,indent=2)
        st.success("Archivée")
'''

















