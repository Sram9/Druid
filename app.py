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
for key, val in {
    'page': 'home', 'coords': None, 'selected_coords': None,
    'selected_name': None, 'show_map': False, 'mistral_calls': [],
    'plant_name': None, 'conversation': []
}.items():
    if key not in state:
        state[key] = val

# --- Identifiant utilisateur ---
st.text_input("👤 Identifiant utilisateur", key="user_id")

# --- Lire coords depuis params URL ---
params = st.query_params
if 'latlon' in params and params['latlon']:
    state.coords = params['latlon'][0]

# --- Si pas de coords, injecter JS pour demander GPS ---
if not state.coords:
    js = '''<script>
if(navigator.geolocation){
  navigator.geolocation.getCurrentPosition(
    pos=>{ const c=pos.coords.latitude+','+pos.coords.longitude;
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
    if st.button(("✅ " if state.page == 'home' else "") + "🌿 Nouvelle identification"):
        state.page = 'home'
    if st.button(("✅ " if state.page == 'archives' else "") + "📚 Archives"):
        state.page = 'archives'
    if st.button(("✅ " if state.page == 'search' else "") + "🔍 Recherche par vertu"):
        state.page = 'search'
    if st.button(("✅ " if state.page == 'map' else "") + "🗺️ Carte des plantes"):
        state.page = 'map'

# --- Page Carte des plantes ---
if state.page == 'map':
    st.title("🗺️ Carte des plantes géolocalisées")
    map_type = st.radio("Afficher :", ["Mes plantes", "Toutes les plantes"])
    user_id = state.get("user_id", "")
    coords_list = []
    for p in archives:
        if map_type == "Mes plantes" and p.get("user") != user_id:
            continue
        if p.get('coords'):
            try:
                lat, lon = map(float, p['coords'].split(','))
                coords_list.append({'lat': lat, 'lon': lon, 'nom': p['nom']})
            except:
                continue
    if coords_list:
        df = pd.DataFrame(coords_list)
    else:
        st.info("Aucune plante géolocalisée pour l'instant. Carte centrée sur votre position si disponible.")
        try:
            lat0, lon0 = map(float, state.coords.split(',')) if state.coords else (46.8, 2.4)
        except:
            lat0, lon0 = 46.8, 2.4
        df = pd.DataFrame([{'lat': lat0, 'lon': lon0}])
    st.map(df)
    st.stop()

# --- Page Archives ---
if state.page == 'archives':
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom", "Date"])
    user_id = state.get("user_id", "")
    filtered_arch = [p for p in archives if p.get("user") == user_id]
    sorted_arch = sorted(filtered_arch, key=lambda p: p['nom'] if order=='Nom' else p['date'])
    for i, p in enumerate(sorted_arch):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                state.selected_coords = p.get('coords')
                state.page = 'map'
                st.rerun()
            if c2.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Plante supprimée")
                st.rerun()
            if c3.button("🔗 Partager", key=f"share{i}"):
                if p.get('coords'):
                    lat, lon = p['coords'].split(',')
                    share_link = f"https://www.google.com/maps?q={lat},{lon}"
                    st.text_input("Lien de partage :", value=share_link, key=f"link{i}")
                else:
                    st.warning("Pas de coordonnées à partager.")
            new_name = c4.text_input("✏️ Nom :", value=p['nom'], key=f"rn{i}")
            if c4.button("💾 Nom", key=f"svn{i}"):
                p['nom'] = new_name
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Nom mis à jour.")
            new_virt = st.text_area("💊 Modifier vertus :", value=p.get('vertus',''), key=f"vrt{i}")
            if st.button("💾 Vertus", key=f"svv{i}"):
                p['vertus'] = new_virt
                open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Vertus mises à jour.")
    st.stop()

# --- Page Recherche ---
if state.page == 'search':
    st.title("🔍 Recherche par vertu")
    keyword = st.text_input("Mot-clé :", "")
    user_id = state.get("user_id", "")
    if keyword:
        results = [p for p in archives if keyword.lower() in p.get('vertus','').lower() and p.get("user") == user_id]
        if results:
            for p in results:
                with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                    st.write(f"🔍 Vertus : {p.get('vertus')}")
                    if st.button("📍 Localiser", key=f"locs_{p['nom']}"):
                        state.selected_coords = p.get('coords')
                        state.page = 'map'
                        st.rerun()
        else:
            st.write("Aucun résultat.")
    st.stop()

# --- Page Identification ---
if state.page == 'home':
    st.title("📷🌿 Identifier une plante + vertus")
    user_id = state.get("user_id", "")
    up = st.file_uploader("Photo", type=["jpg","jpeg","png"])
    if up:
        img_bytes = up.read()
        st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
        try:
            resp = requests.post(
                f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                files={"images":(up.name,io.BytesIO(img_bytes),mimetypes.guess_type(up.name)[0] or 'image/jpeg')},
                data={"organs":"leaf"}, timeout=10)
            resp.raise_for_status()
            sug = resp.json().get('results',[])[:3]
            for idx, s in enumerate(sug,1):
                sci = s['species']['scientificNameWithoutAuthor']
                if st.button(f"{idx}. {sci}", key=f"sugg{idx}"):
                    state.plant_name = sci
                    state.mistral_calls = []
            if state.plant_name is None and sug:
                state.plant_name = sug[0]['species']['scientificNameWithoutAuthor']
        except:
            st.warning("PlantNet failed, fallback to Plant.id")
            j = requests.post("https://api.plant.id/v2/identify", headers={"Api-Key":PLANTID_API_KEY}, files={"images":img_bytes}).json()
            state.plant_name = j['suggestions'][0]['plant_name']
            st.write(state.plant_name)

        name = state.plant_name
        if name:
            if name in cache:
                v = cache[name]
            else:
                now = datetime.utcnow()
                state.mistral_calls = [t for t in state.mistral_calls if now - t < timedelta(seconds=60)]
                if len(state.mistral_calls) < 3:
                    body = {"model":"mistral-tiny","messages":[{"role":"user","content":f"Cette plante '{name}', comestible, vertus médicinales?"}],"max_tokens":300}
                    h = {"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
                    j = requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=body).json()
                    v = j['choices'][0]['message']['content']
                    cache[name] = v
                    open(CACHE_PATH,'w').write(json.dumps(cache,ensure_ascii=False,indent=2))
                    state.mistral_calls.append(now)
                else:
                    v = "Limite atteinte."
            st.markdown(f"### 🌿 Vertus de **{name}**")
            st.write(v)
            q = st.text_input("❓ Autre question ?", key="extra_q")
            if q:
                body = {"model":"mistral-tiny","messages":[{"role":"user","content":f"À propos de '{name}', {q}"}],"max_tokens":300}
                h = {"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
                ans = requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=body).json()
                st.write(ans['choices'][0]['message']['content'])
            if st.button("✅ Archiver cette plante"):
                archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":state.coords,"vertus":v,"user":user_id})
                open(ARCHIVES_PATH,'w').write(json.dumps(archives,ensure_ascii=False,indent=2))
                st.success("Archivée !")









































