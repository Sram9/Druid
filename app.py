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
if 'coords' not in state: state.coords = None
if 'selected_coords' not in state: state.selected_coords = None
if 'selected_name' not in state: state.selected_name = None
if 'show_map' not in state: state.show_map = False
if 'mistral_calls' not in state: state.mistral_calls = []
if 'plant_name' not in state: state.plant_name = None

# --- Lire coords depuis params URL ---
params = st.query_params
if 'latlon' in params and params['latlon']:
    state.coords = params['latlon'][0]

# --- Si pas de coords, injecter JS pour demander GPS ---
if not state.coords:
    js = '''<script>
if(navigator.geolocation){
  navigator.geolocation.getCurrentPosition(
    pos=>{
      const c=pos.coords.latitude+','+pos.coords.longitude;
      const url=window.location.pathname+'?latlon='+c;
      window.history.replaceState({},'',url);
      window.location.reload();
    },
    err=>{
      console.warn(err);
      alert("Erreur de géolocalisation : " + err.message);
    },
    {
      enableHighAccuracy: true,  // Demander une précision plus élevée
      timeout: 5000,             // Temps limite de 5 secondes pour obtenir la position
      maximumAge: 0             // Toujours demander la position actuelle
    }
  );
}
</script>'''
    st.components.v1.html(js)

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if state.page=='home' else "") + "🌿 Nouvelle identification"):
        state.page='home'
    if st.button(("✅ " if state.page=='archives' else "") + "📚 Archives"):
        state.page='archives'
    if st.button(("✅ " if state.page=='search' else "") + "🔍 Recherche par vertu"):
        state.page = 'search'

# --- Archives page ---
if state.page=='archives':
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom","Date"])
    sorted_archives = sorted(archives, key=lambda p: p['nom'] if order=='Nom' else p['date'])
    for i,p in enumerate(sorted_archives):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1,c2,c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                state.selected_coords = p.get('coords')
                state.selected_name = p['nom']
                state.show_map = True
            if c2.button("🔍 Vertus", key=f"virt{i}"):
                st.write(p.get('vertus','Aucune vertu enregistrée'))
            if c3.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.experimental_rerun = None
                state.page='archives'
            new = st.text_input("✏️ Renommer :", value=p['nom'], key=f"rn{i}")
            if st.button("💾 Enregistrer nom", key=f"sv{i}"):
                p['nom']=new
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Nom mis à jour")
    if state.show_map:
        st.markdown("---")
        st.markdown(f"### 🗺️ Localisation de : {state.selected_name}")
        if state.selected_coords:
            try:
                lat,lon = state.selected_coords.split(',')
                df = pd.DataFrame([{'lat':float(lat),'lon':float(lon)}])
                st.map(df)
                link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                st.markdown(f"[🧭 Démarrer la navigation]({link})")
            except:
                st.error("⚠️ Coordonnées invalides.")
        else:
            st.error("⚠️ Aucune coordonnée disponible.")
        if st.button("🔙 Retour archives"):
            state.show_map=False
    st.stop()

# --- Recherche par vertu page ---
if state.page == 'search':
    st.title("🔍 Recherche par vertu")
    search_term = st.text_input("🔎 Recherche de vertu", "")
    if search_term:
        results = [p for p in archives if search_term.lower() in p.get('vertus', '').lower()]
        if results:
            for p in results:
                with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                    st.write(f"📅 {p['date']}")
                    st.write(p.get('vertus', 'Aucune vertu enregistrée'))
                    if p.get('coords'):
                        st.write(f"📍 Coordonnées : {p['coords']}")
                    else:
                        st.write("⚠️ Pas de coordonnées disponibles.")
        else:
            st.write("Aucun résultat trouvé.")
    st.stop()

# --- Identification page ---
state.page='home'
st.title("📷🌿 Identifier une plante + vertus")
up = st.file_uploader("Photo", type=["jpg","jpeg","png"])
if up:
    img_bytes = up.read()
    st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
    # PlantNet
    try:
        resp = requests.post(
            f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
            files={"images":(up.name,io.BytesIO(img_bytes),mimetypes.guess_type(up.name)[0] or 'image/jpeg')},
            data={"organs":"leaf"}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get('results',[])
        sug = results[:3]
        # Afficher suggestions cliquables
        for idx,s in enumerate(sug,1):
            sci=s['species']['scientificNameWithoutAuthor']
            prob=round(s['score']*100,1)
            if st.button(f"{idx}. {sci} ({prob}%)", key=f"sugg{idx}"):
                state.plant_name = sci
                state.mistral_calls = []
        # Default
        if state.plant_name is None and sug:
            state.plant_name = sug[0]['species']['scientificNameWithoutAuthor']
    except:
        st.warning("PlantNet failed, use Plant.id")
        j = requests.post("https://api.plant.id/v2/identify", headers={"Api-Key":PLANTID_API_KEY}, files={"images":img_bytes}).json()
        s=j['suggestions'][0]; name=s['plant_name']
        st.write(f"{name} ({s['probability']*100:.1f}%)")
        state.plant_name=name
    # Mistral
    name=state.plant_name
    if name in cache:
        v=cache[name]
    else:
        now=datetime.utcnow()
        state.mistral_calls=[t for t in state.mistral_calls if now-t<timedelta(seconds=60)]
        if len(state.mistral_calls)<3:
            body={"model":"mistral-tiny","messages":[{"role":"user","content":f"Nom courant {name}, comestible, vertus médicinales?"}], "max_tokens":200}
            h={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
            j=requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=body).json()
            v=j['choices'][0]['message']['content']; cache[name]=v; open(CACHE_PATH,'w').write(json.dumps(cache,ensure_ascii=False,indent=2))
            state.mistral_calls.append(now)
        else:
            v="Limite atteinte"
    st.markdown(f"### 🌿 Vertus de **{name}**")
    st.write(v)
    # Archiver
    if st.button("✅ Archiver cette plante"):
        if state.coords:
            archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":state.coords,"vertus":v})
            open(ARCHIVES_PATH,'w').write(json.dumps(archives,ensure_ascii=False,indent=2))
            st.success("Plante archivée avec succès!")
        else:
            st.error("⚠️ Les coordonnées GPS ne sont pas disponibles.")






























