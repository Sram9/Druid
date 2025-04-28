import streamlit as st
import folium
from streamlit_folium import folium_static  # Pour afficher la carte interactive dans Streamlit
import json
import os
from datetime import datetime

# Charger les archives depuis le fichier
ARCHIVES_PATH = "archives.json"
archives = json.load(open(ARCHIVES_PATH, "r", encoding="utf-8")) if os.path.exists(ARCHIVES_PATH) else []

# --- Initialisation de la page Streamlit ---
st.set_page_config(page_title="Plante + Vertus", layout="centered")

# --- Session state defaults ---
state = st.session_state
if 'page' not in state: state.page = 'home'

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if state.page == 'home' else "") + "🌿 Nouvelle identification"):
        state.page = 'home'
    if st.button(("✅ " if state.page == 'archives' else "") + "📚 Archives"):
        state.page = 'archives'
    if st.button(("✅ " if state.page == 'search' else "") + "🔍 Recherche par vertu"):
        state.page = 'search'

# --- Archives page ---
if state.page == 'archives':
    st.title("📚 Plantes archivées")
    order = st.radio("Trier par :", ["Nom", "Date"])
    sorted_archives = sorted(archives, key=lambda p: p['nom'] if order == 'Nom' else p['date'])
    
    # Afficher la carte avec les marqueurs pour les plantes archivées
    st.subheader("🗺️ Carte des plantes archivées")
    
    # Fonction pour afficher la carte avec les marqueurs des archives
    def show_map_with_markers(archives):
        # Initialisation de la carte
        m = folium.Map(location=[48.8566, 2.3522], zoom_start=12)  # Par défaut, centré sur Paris
        
        # Ajouter des marqueurs pour chaque plante archivée
        for plant in archives:
            coords = plant.get('coords')
            if coords:
                lat, lon = map(float, coords.split(','))
                # Ajouter un marqueur pour chaque plante
                folium.Marker([lat, lon], popup=plant['nom']).add_to(m)

        # Afficher la carte
        folium_static(m)

    # Afficher les marqueurs sur la carte
    show_map_with_markers(archives)
    
    # Affichage des plantes archivées sous forme de liste
    for i, p in enumerate(sorted_archives):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                st.write(f"🔹 Coordonnées: {p.get('coords', 'Aucune coordonnée disponible')}")
            if c2.button("🔍 Vertus", key=f"virt{i}"):
                st.write(p.get('vertus', 'Aucune vertu enregistrée'))
            if c3.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                open(ARCHIVES_PATH, 'w', encoding='utf-8').write(json.dumps(archives, ensure_ascii=False, indent=2))
                st.experimental_rerun()

# --- Recherche par vertu page ---
if state.page == 'search':
    st.title("🔍 Recherche par vertu")
    keyword = st.text_input("Saisir un mot-clé pour rechercher une vertu", "")
    if keyword:
        # Filtrer les plantes archivées contenant le mot-clé dans les vertus
        results = [p for p in archives if keyword.lower() in (p.get('vertus', '').lower())]
        if results:
            for p in results:
                with st.expander(f"{p['nom']} ({p['date'][:10]})"):
                    st.write(f"📅 {p['date']}")
                    st.write(f"🔍 Vertus : {p.get('vertus', 'Aucune vertu enregistrée')}")
                    c1, c2 = st.columns(2)
                    if c1.button("📍 Localiser", key=f"loc_{p['nom']}"):
                        st.write(f"🔹 Coordonnées: {p.get('coords', 'Aucune coordonnée disponible')}")
                    if c2.button("❌ Supprimer", key=f"del_{p['nom']}"):
                        archives.remove(p)
                        open(ARCHIVES_PATH, 'w', encoding='utf-8').write(json.dumps(archives, ensure_ascii=False, indent=2))
                        st.experimental_rerun()
        else:
            st.write(f"Aucune plante trouvée avec le mot-clé '{keyword}' dans les vertus.")
    if st.button("🔙 Retour archives"):
        state.page = 'archives'

# --- Identification page ---
if state.page == 'home':
    st.title("📷🌿 Identifier une plante + vertus")
    # Le reste du code d'identification de plante ici






































