# app.py
import streamlit as st
import requests, json, io, base64, mimetypes
from datetime import datetime, timedelta
from PIL import Image
import pandas as pd

# --- Constantes et chemins ---
PLANTNET_API_KEY = "your_plantnet_api_key"
MISTRAL_API_KEY = "your_mistral_api_key"
ARCHIVES_PATH = "archives.json"
CACHE_PATH = "cache.json"

# --- Initialisation ---
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user_id" not in st.session_state:
    st.session_state.user_id = str(datetime.now().timestamp())
if "coords" not in st.session_state:
    st.session_state.coords = None
if "archives" not in st.session_state:
    try:
        with open(ARCHIVES_PATH, 'r', encoding='utf-8') as f:
            st.session_state.archives = json.load(f)
    except:
        st.session_state.archives = []
if "cache" not in st.session_state:
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            st.session_state.cache = json.load(f)
    except:
        st.session_state.cache = {}

# --- Barre latérale ---
st.sidebar.title("🌿 Menu")
st.session_state.page = st.sidebar.radio("Navigation", ["home", "map", "archives", "search"],
                                         format_func=lambda x: {"home": "Identifier", "map": "Carte", "archives": "Archives", "search": "Recherche"}[x])

# --- Page Carte ---
if st.session_state.page == "map":
    st.title("🗺️ Carte des plantes géolocalisées")
    map_type = st.radio("Afficher :", ["Mes plantes", "Toutes les plantes"])
    user_id = st.session_state.user_id
    coords_list = []
    for p in st.session_state.archives:
        if map_type == "Mes plantes" and p.get("user") != user_id:
            continue
        if p.get("coords"):
            try:
                lat, lon = map(float, p['coords'].split(','))
                coords_list.append({'lat': lat, 'lon': lon, 'nom': p['nom']})
            except:
                continue
    if coords_list:
        df = pd.DataFrame(coords_list)
    else:
        lat0, lon0 = 46.8, 2.4
        df = pd.DataFrame([{'lat': lat0, 'lon': lon0}])
        st.info("Aucune plante géolocalisée pour l'instant. Carte centrée sur la France.")
    st.map(df)
    st.stop()

# --- Page Archives ---
if st.session_state.page == "archives":
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom", "Date"])
    user_id = st.session_state.user_id
    filtered_arch = [p for p in st.session_state.archives if p.get("user") == user_id]
    sorted_arch = sorted(filtered_arch, key=lambda p: p['nom'] if order == 'Nom' else p['date'])
    for i, p in enumerate(sorted_arch):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            if "image" in p:
                st.image(Image.open(io.BytesIO(base64.b64decode(p['image']))), caption=p['nom'])
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                st.session_state.selected_coords = p.get('coords')
                st.session_state.page = 'map'
                st.rerun()
            if c2.button("❌ Supprimer", key=f"del{i}"):
                st.session_state.archives.remove(p)
                with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.archives, f, ensure_ascii=False, indent=2)
                st.success("Plante supprimée")
                st.rerun()
            if c3.button("🔗 Partager", key=f"share{i}"):
                if p.get('coords'):
                    lat, lon = p['coords'].split(',')
                    st.text_input("Lien de partage :", value=f"https://www.google.com/maps?q={lat},{lon}", key=f"link{i}")
                else:
                    st.warning("Pas de coordonnées à partager.")
            new_name = c4.text_input("✏️ Nom :", value=p['nom'], key=f"rn{i}")
            if c4.button("💾 Nom", key=f"svn{i}"):
                p['nom'] = new_name
                with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.archives, f, ensure_ascii=False, indent=2)
                st.success("Nom mis à jour.")
            new_virt = st.text_area("💊 Modifier vertus :", value=p.get('vertus',''), key=f"vrt{i}")
            if st.button("💾 Vertus", key=f"svv{i}"):
                p['vertus'] = new_virt
                with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.archives, f, ensure_ascii=False, indent=2)
                st.success("Vertus mises à jour.")
    st.stop()

# --- Page Recherche ---
if st.session_state.page == "search":
    st.title("🔍 Recherche par vertu")
    keyword = st.text_input("Mot-clé :")
    if keyword:
        results = [p for p in st.session_state.archives if keyword.lower() in p.get('vertus','').lower() and p.get("user") == st.session_state.user_id]
        if results:
            for p in results:
                with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                    st.write(f"🔍 Vertus : {p.get('vertus')}")
                    if st.button("📍 Localiser", key=f"locs_{p['nom']}"):
                        st.session_state.selected_coords = p.get('coords')
                        st.session_state.page = 'map'
                        st.rerun()
        else:
            st.write("Aucun résultat.")
    st.stop()

# --- Page Identification avec suggestions et chat ---
if st.session_state.page == "home":
    st.title("📷🌿 Identifier une plante et connaître ses vertus")
    user_id = st.session_state.user_id
    up = st.file_uploader("Photo", type=["jpg", "jpeg", "png"])

    if up:
        img_bytes = up.read()
        st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)

        if "suggestions" not in st.session_state:
            try:
                resp = requests.post(
                    f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                    files={"images": (up.name, io.BytesIO(img_bytes), mimetypes.guess_type(up.name)[0] or 'image/jpeg')},
                    data={"organs": "leaf"}, timeout=10)
                resp.raise_for_status()
                results = resp.json().get('results', [])[:3]
                st.session_state.suggestions = [
                    {"sci": r['species']['scientificNameWithoutAuthor'], "score": r['score']} for r in results
                ]
                st.session_state.img_bytes = img_bytes
            except:
                st.error("Échec de l'identification.")

    if "suggestions" in st.session_state:
        st.subheader("Suggestions PlantNet")
        for idx, s in enumerate(st.session_state.suggestions):
            if st.button(f"{idx+1}. {s['sci']} ({s['score']*100:.1f}%)"):
                st.session_state.plant_name = s["sci"]
                st.session_state.chat_history = []
                st.session_state.vertus = None

    name = st.session_state.get("plant_name")
    if name:
        st.markdown(f"## 🌿 Vertus de **{name}**")
        if not st.session_state.get("vertus"):
            prompt = f"Cette plante s'appelle '{name}'. Est-elle comestible ou a-t-elle des vertus médicinales et, si oui, comment est-elle utilisée ?"
            body = {"model": "mistral-tiny", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300}
            h = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
            r = requests.post("https://api.mistral.ai/v1/chat/completions", headers=h, json=body).json()
            st.session_state.vertus = r['choices'][0]['message']['content']
        st.write(st.session_state.vertus)

        q = st.text_input("❓ Autre question ?", key="extra_q")
        if q:
            prompt = f"À propos de '{name}', {q}"
            body = {"model": "mistral-tiny", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300}
            h = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
            ans = requests.post("https://api.mistral.ai/v1/chat/completions", headers=h, json=body).json()
            st.session_state.chat_history.append((q, ans['choices'][0]['message']['content']))

        for question, reponse in st.session_state.chat_history:
            st.markdown(f"**Vous :** {question}")
            st.markdown(f"**Mistral :** {reponse}")

        if st.button("✅ Archiver cette plante"):
            st.session_state.archives.append({
                "nom": name,
                "date": datetime.now().isoformat(),
                "coords": st.session_state.coords,
                "vertus": st.session_state.vertus,
                "user": user_id,
                "image": base64.b64encode(st.session_state.img_bytes).decode()
            })
            with open(ARCHIVES_PATH, 'w', encoding='utf-8') as f:
                json.dump(st.session_state.archives, f, ensure_ascii=False, indent=2)
            st.success("Archivée !")
            for key in ["plant_name", "suggestions", "vertus", "chat_history", "img_bytes"]:
                st.session_state.pop(key, None)
            st.experimental_rerun()


















































