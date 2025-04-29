import streamlit as st
import requests
import os
import io
import json
import mimetypes
import base64
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
    'plant_name': None, 'conversation': [], 'latest_plant': None,
    'archive_requested': False
}.items():
    if key not in state:
        state[key] = val

# --- Identifiant utilisateur ---
if "user_id" not in state:
    st.text_input("👤 Identifiant utilisateur", key="user_id")
else:
    st.text_input("👤 Identifiant utilisateur", key="user_id", value=state.user_id, disabled=True)

# --- Lire coords depuis params URL ---
params = st.query_params
if 'latlon' in params and params['latlon']:
    state.coords = params['latlon'][0]

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if state.page == 'home' else "") + "🌿 Nouvelle identification"):
        state.page = 'home'
    if st.button(("✅ " if state.page == 'archives' else "") + "📚 Archives"):
        state.page = 'archives'
    if st.button(("✅ " if state.page == 'search' else "") + "🔍 Recherche par vertu"):
        state.page = 'search'
    if st.button(("✅ " if state.page == 'map' else "") + "🗺️ Mes plantes" if state.get("user_id") else "🗺️ Carte des plantes"):
        state.page = 'map'

# --- Page Carte des plantes ---
if state.page == 'map':
    st.title("🗺️ Carte des plantes géolocalisées")
    map_type = st.radio("Afficher :", ["Mes plantes", "Toutes les plantes"])
    user_id = state.get("user_id") or ""

    if map_type == "Mes plantes" and not user_id:
        st.warning("Veuillez saisir un identifiant utilisateur pour afficher vos plantes.")
        st.stop()

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

# (le reste du code reste inchangé)













































