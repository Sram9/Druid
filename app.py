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

# --- Fonctions utilitaires ---
def save_archives():
    with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
        json.dump(archives, f, ensure_ascii=False, indent=2)

def save_cache():
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# --- Charger ou initialiser cache et archives ---
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
    err=>console.warn(err)
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
    if st.button(("✅ " if state.page=='search' else "") + "🔍 Recherche par vertu ou nom"):
        state.page='search'

# --- Archives page ---
if state.page=='archives':
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom", "Date"])
    sorted_archives = sorted(archives, key=lambda p: p['nom'] if order == 'Nom' else p['date'])
    for i, p in enumerate(sorted_archives):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                state.selected_coords = p.get('coords')
                state.selected_name = p['nom']
                state.show_map = True
            if c2.button("🔍 Vertus", key=f"virt{i}"):
                st.write(p.get('vertus', 'Aucune vertu enregistrée'))
            if c3.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                save_archives()
                st.experimental_rerun = None  # Ne pas modifier comme demandé
                state.page = 'archives'
            new = st.text_input("✏️ Renommer :", value=p['nom'], key=f"rn{i}")
            if st.button("💾 Enregistrer nom", key=f"sv{i}"):
                p['nom'] = new
                save_archives()
                st.success("Nom mis à jour")
            edited_virtues = st.text_area("✏️ Modifier vertus :", value=p.get('vertus', ''), key=f"virt_edit{i}")
            if st.button("💾 Sauvegarder vertus", key=f"save_virt{i}"):
                p['vertus'] = edited_virtues
                save_archives()
                st.success("Vertus mises à jour")
    if state.show_map:
        st.markdown("---")
        st.markdown(f"### 🗺️ Localisation de : {state.selected_name}")
        if state.selected_coords:
            try:
                lat, lon = state.selected_coords.split(',')
                df = pd.DataFrame([{'lat': float(lat), 'lon': float(lon)}])
                st.map(df)
                link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                st.markdown(f"[🧭 Démarrer la navigation]({link})")
            except:
                st.error("⚠️ Coordonnées invalides.")
        else:
            st.error("⚠️ Aucune coordonnée disponible.")
        if st.button("🔙 Retour archives"):
            state.show_map = False
    st.stop()

# --- Recherche par vertu ou nom page ---
if state.page == 'search':
    st.title("🔍 Recherche par vertu ou nom")
    keyword = st.text_input("Saisir un mot-clé pour rechercher une vertu ou un nom de plante", "")
    if keyword:
        results = [p for p in archives if keyword.lower() in (p.get('vertus', '').lower() + p['nom'].lower())]
        if results:
            for p in results:
                with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                    st.write(f"📅 {p['date']}")
                    st.write(f"🔍 Vertus : {p.get('vertus', 'Aucune vertu enregistrée')}")
                    c1, c2 = st.columns(2)
                    if c1.button("📍 Localiser", key=f"loc_{p['nom']}"):
                        state.selected_coords = p.get('coords')
                        state.selected_name = p['nom']
                        state.show_map = True
                    if c2.button("❌ Supprimer", key=f"del_{p['nom']}"):
                        archives.remove(p)
                        save_archives()
                        st.experimental_rerun = None
                        state.page = 'search'
        else:
            st.write(f"Aucune plante trouvée avec le mot-clé '{keyword}'.")
    if st.button("🔙 Retour archives"):
        state.page = 'archives'

# --- Identification page ---
if state.page == 'home':
    st.title("📷🌿 Identifier une plante + vertus")
    nb_suggestions = st.sidebar.slider("Nombre de suggestions", 1, 5, 3)
    up = st.file_uploader("Photo", type=["jpg", "jpeg", "png"])
    if up:
        img_bytes = up.read()
        st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
        try:
            resp = requests.post(
                f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                files={"images": (up.name, io.BytesIO(img_bytes), mimetypes.guess_type(up.name)[0] or 'image/jpeg')},
                data={"organs": "leaf"}, timeout=10)
            resp.raise_for_status()
            results = resp.json().get('results', [])
            sug = results[:nb_suggestions]
            for idx, s in enumerate(sug, 1):
                sci = s['species']['scientificNameWithoutAuthor']
                prob = round(s['score'] * 100, 1)
                if st.button(f"{idx}. {sci} ({prob}%)", key=f"sugg{idx}"):
                    state.plant_name = sci
                    state.mistral_calls = []
            if state.plant_name is None and sug:
                state.plant_name = sug[0]['species']['scientificNameWithoutAuthor']
        except:
            st.warning("PlantNet a échoué, utilisation de Plant.id")
            j = requests.post("https://api.plant.id/v2/identify", headers={"Api-Key": PLANTID_API_KEY},
                              files={"images": img_bytes}).json()
            s = j['suggestions'][0]
            name = s['plant_name']
            st.write(f"{name} ({s['probability'] * 100:.1f}%)")
            state.plant_name = name
        name = state.plant_name
        if name in cache:
            v = cache[name]
        else:
            now = datetime.utcnow()
            state.mistral_calls = [t for t in state.mistral_calls if now - t < timedelta(seconds=60)]
            if len(state.mistral_calls) < 3:
                body = {
                    "model": "mistral-tiny",
                    "messages": [{"role": "user",
                                  "content": f"Indique si {name} est comestible ou possède des vertus médicinales, et explique comment cette plante est utilisée traditionnellement."}],
                    "max_tokens": 300}
                h = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
                j = requests.post("https://api.mistral.ai/v1/chat/completions", headers=h, json=body).json()
                v = j['choices'][0]['message']['content']
                cache[name] = v
                save_cache()
                state.mistral_calls.append(now)
            else:
                v = "Limite d'appels atteinte. Merci de patienter."
        st.markdown(f"### 🌿 Vertus de **{name}**")
        st.write(v)
        if st.button("✅ Archiver cette plante"):
            archives.append({"nom": name, "date": datetime.now().isoformat(), "coords": state.coords, "vertus": v})
            save_archives()
            st.success("Plante archivée !")










































