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
if "user_id" not in state:
    st.text_input("👤 Identifiant utilisateur", key="user_id")
else:
    st.text_input("👤 Identifiant utilisateur", key="user_id", value=state.user_id, disabled=True)

# --- Lire coords depuis params URL ---
params = st.experimental_get_query_params()
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
    if map_type == "Mes plantes":
        st.write(f"👤 Mes plantes - Utilisateur : **{user_id}**")
    coords_list = []
    for p in archives:
        if map_type == "Mes plantes" and p.get("user") != user_id:
            continue
        if p.get('coords'):
            try:
                lat, lon = map(float, p['coords'].split(','))
                label = f"{p['nom']} (👤 {p.get('user', 'inconnu')})"
                coords_list.append({'lat': lat, 'lon': lon, 'nom': label})
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
            if 'image' in p:
                try:
                    image_bytes = p['image'].encode('latin1') if isinstance(p['image'], str) else p['image']
                    with io.BytesIO(image_bytes) as buf:
                        img = Image.open(buf)
                        st.image(img, caption="Photo de la plante", use_container_width=True)
                except Exception as e:
                    st.warning("Erreur d'affichage de l'image : " + str(e))
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
            if c3.button("📌 Partager sur carte commune", key=f"share{i}"):
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

# --- Page Recherche par vertu ---
if state.page == 'search':
    st.title("🔍 Recherche par vertu médicinale")
    query = st.text_input("Entrez une vertu (ex : digestion, sommeil...) 🧪")
    if query:
        results = [p for p in archives if query.lower() in p.get('vertus', '').lower() and p.get("user") == state.user_id]
        if not results:
            st.warning("Aucun résultat trouvé dans vos archives.")
        for p in results:
            with st.expander(f"🌿 {p['nom']} ({p['date'][:10]})"):
                st.markdown(p.get("vertus", "Aucune information."))

# --- Page Accueil / Identification ---
if state.page == 'home':
    st.title("🌿 Identifier une plante et découvrir ses vertus")
    uploaded_file = st.file_uploader("Choisissez une photo de plante à identifier 📷", type=['jpg', 'jpeg', 'png'])
    if uploaded_file:
        st.image(uploaded_file, caption="Image sélectionnée", use_container_width=True)
        if st.button("🔍 Identifier cette plante"):
            image_bytes = uploaded_file.read()

            # --- Appel Plant.id ---
            headers = {'Content-Type': 'application/json', 'Api-Key': PLANTID_API_KEY}
            data = {
                "images": ["data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()],
                "organs": ["leaf"]
            }
            response = requests.post("https://api.plant.id/v2/identify", headers=headers, json=data)
            if response.ok:
                suggestions = response.json().get("suggestions", [])
                if suggestions:
                    best_match = suggestions[0]
                    state.plant_name = best_match["plant_name"]
                    st.success(f"🌿 Plante identifiée : **{state.plant_name}**")

                    # --- Requête à Mistral ---
                    question = f"Cette plante est-elle comestible ou a-t-elle des vertus médicinales et, si oui, comment est-elle utilisée ? Nom : {state.plant_name}"
                    mistral_headers = {
                        "Authorization": f"Bearer {MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    mistral_data = {
                        "model": "mistral-small",
                        "messages": [
                            {"role": "user", "content": question}
                        ]
                    }
                    r = requests.post("https://api.mistral.ai/v1/chat/completions", headers=mistral_headers, json=mistral_data)
                    if r.ok:
                        answer = r.json()['choices'][0]['message']['content']
                        st.markdown(f"### 💊 Vertus médicinales proposées :\n{answer}")
                        # Archive locale
                        archives.append({
                            "nom": state.plant_name,
                            "date": datetime.now().isoformat(),
                            "image": image_bytes.decode('latin1'),
                            "coords": state.coords,
                            "vertus": answer,
                            "user": state.user_id
                        })
                        with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
                            json.dump(archives, f, ensure_ascii=False, indent=2)
                        st.success("🌱 Plante archivée avec succès.")
                    else:
                        st.error("Erreur lors de la requête à Mistral.")
                else:
                    st.warning("Aucune plante reconnue.")
            else:
                st.error("Erreur lors de l'identification via Plant.id.")










































