import streamlit as st
import requests
import json
import base64
import io
from PIL import Image
from datetime import datetime, timedelta

# Configuration et initialisation
ARCHIVES_PATH = "archives.json"
CACHE_PATH = "cache.json"
PLANTNET_API_KEY = st.secrets["PLANTNET_API_KEY"]
MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]

# Variables de session
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "plant_name" not in st.session_state:
    st.session_state.plant_name = None
if "mistral_calls" not in st.session_state:
    st.session_state.mistral_calls = []

# --- Page Identification ---
if st.session_state.page == 'home':
    st.title("📷🌿 Identifier une plante + vertus")
    user_id = st.session_state.user_id

    # Téléversement de l'image
    up = st.file_uploader("Téléchargez une photo", type=["jpg", "jpeg", "png"])
    if up:
        img_bytes = up.read()
        st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
        
        # Identification via PlantNet
        try:
            resp = requests.post(
                f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                files={"images":(up.name, io.BytesIO(img_bytes), "image/jpeg")},
                data={"organs": "leaf"}, timeout=10)
            resp.raise_for_status()
            suggestions = resp.json().get('results', [])[:3]
            for idx, s in enumerate(suggestions, 1):
                sci = s['species']['scientificNameWithoutAuthor']
                confidence = s['score'] * 100
                if st.button(f"{idx}. {sci} ({confidence:.2f}%)", key=f"sugg{idx}"):
                    st.session_state.plant_name = sci
                    st.session_state.mistral_calls = []
        except Exception as e:
            st.warning(f"PlantNet a échoué, tentative avec Plant.id : {e}")
            j = requests.post("https://api.plant.id/v2/identify", headers={"Api-Key": st.secrets["PLANTID_API_KEY"]}, files={"images": img_bytes}).json()
            st.session_state.plant_name = j['suggestions'][0]['plant_name']
            st.write(st.session_state.plant_name)

        # Interaction avec Mistral pour obtenir les vertus
        name = st.session_state.plant_name
        if name:
            if name in st.session_state.mistral_calls:
                v = "Limite atteinte pour les requêtes."
            else:
                body = {"model": "mistral-tiny", "messages": [{"role": "user", "content": f"Cette plante '{name}', comestible, vertus médicinales?"}], "max_tokens": 300}
                h = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
                j = requests.post("https://api.mistral.ai/v1/chat/completions", headers=h, json=body).json()
                v = j['choices'][0]['message']['content']
                st.session_state.mistral_calls.append(name)

            st.markdown(f"### 🌿 Vertus de **{name}**")
            st.write(v)

            # Boîte de dialogue pour poser d'autres questions
            q = st.text_input("❓ Autre question ?", key="extra_q")
            if q:
                body = {"model": "mistral-tiny", "messages": [{"role": "user", "content": f"À propos de '{name}', {q}"}], "max_tokens": 300}
                ans = requests.post("https://api.mistral.ai/v1/chat/completions", headers=h, json=body).json()
                st.write(ans['choices'][0]['message']['content'])

            # Option pour archiver la plante
            if st.button("✅ Archiver cette plante"):
                archive_entry = {
                    "nom": name,
                    "date": datetime.now().isoformat(),
                    "coords": st.session_state.coords,
                    "vertus": v,
                    "user": user_id,
                    "image": base64.b64encode(img_bytes).decode()
                }
                with open(ARCHIVES_PATH, 'a') as f:
                    f.write(json.dumps(archive_entry) + "\n")
                st.success("Plante archivée !")

    st.stop()

# --- Page Archives ---
if st.session_state.page == 'archives':
    st.title("📚 Plantes archivées")
    user_id = st.session_state.user_id
    try:
        with open(ARCHIVES_PATH) as f:
            archives = [json.loads(line) for line in f.readlines()]
        user_archives = [p for p in archives if p['user'] == user_id]
        for p in user_archives:
            with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                st.image(base64.b64decode(p['image']), width=150)
                st.write(f"📅 {p['date']}")
                st.write(f"🔍 Vertus : {p['vertus']}")
                st.markdown("---")
    except FileNotFoundError:
        st.warning("Aucune archive trouvée.")
    
    st.stop()

# --- Page Carte ---
if st.session_state.page == 'map':
    st.title("🗺️ Carte des plantes géolocalisées")
    map_type = st.radio("Afficher :", ["Mes plantes", "Toutes les plantes"])
    user_id = st.session_state.user_id
    coords_list = []
    try:
        with open(ARCHIVES_PATH) as f:
            archives = [json.loads(line) for line in f.readlines()]
        for p in archives:
            if map_type == "Mes plantes" and p.get("user") != user_id:
                continue
            if p.get('coords'):
                coords_list.append({'lat': p['coords'][0], 'lon': p['coords'][1], 'nom': p['nom']})
    except FileNotFoundError:
        pass
    
    if coords_list:
        df = pd.DataFrame(coords_list)
        st.map(df)
    else:
        st.info("Aucune plante géolocalisée pour l'instant.")
    
    st.stop()

# --- Page Recherche ---
if st.session_state.page == 'search':
    st.title("🔍 Recherche par vertu")
    keyword = st.text_input("Mot-clé :", "")
    user_id = st.session_state.user_id
    try:
        with open(ARCHIVES_PATH) as f:
            archives = [json.loads(line) for line in f.readlines()]
        if keyword:
            results = [p for p in archives if keyword.lower() in p.get('vertus', '').lower() and p.get("user") == user_id]
            if results:
                for p in results:
                    with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                        st.write(f"🔍 Vertus : {p.get('vertus')}")
            else:
                st.write("Aucun résultat trouvé.")
    except FileNotFoundError:
        st.warning("Aucune archive trouvée.")
    
    st.stop()



















































