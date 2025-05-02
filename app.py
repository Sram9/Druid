# streamlit_app.py
import streamlit as st
import json
import os
import base64
import io
from PIL import Image
from datetime import datetime

# --- Chemins des fichiers ---
ARCHIVES_FILE = "archives.json"

# --- Initialisation des archives ---
if "archives" not in st.session_state:
    if os.path.exists(ARCHIVES_FILE):
        with open(ARCHIVES_FILE, "r", encoding="utf-8") as f:
            st.session_state.archives = json.load(f)
    else:
        st.session_state.archives = []

# --- Barre latérale ---
st.sidebar.title("🌿 Menu")
page = st.sidebar.radio("Navigation", ["identifier", "archives"], format_func=lambda p: {"identifier": "Identifier", "archives": "Archives"}[p])

# --- Page Archives ---
if page == "archives":
    st.title("📚 Mes plantes archivées")
    order = st.radio("Trier par :", ["Nom", "Date"])

    sorted_archives = sorted(
        st.session_state.archives,
        key=lambda x: x["nom"].lower() if order == "Nom" else x["date"],
        reverse=(order == "Date")
    )

    for i, plante in enumerate(sorted_archives):
        st.markdown("---")
        st.subheader(f"{plante['nom']} ({plante['date'][:10]})")

        # Affichage image
        if "image" in plante:
            try:
                image_bytes = base64.b64decode(plante['image'])
                image = Image.open(io.BytesIO(image_bytes))
                st.image(image, use_column_width=True)
            except Exception as e:
                st.warning("❌ Image non lisible.")

        # Infos supplémentaires
        st.markdown(f"**📅 Date :** {plante['date']}")
        st.markdown(f"**📍 Coordonnées :** {plante.get('coords', 'Non précisées')}")
        st.markdown(f"**💊 Vertus :** {plante.get('vertus', 'Non renseignées')}")

# --- Page Identifier ---
elif page == "identifier":
    st.title("📷 Identifier une plante")

    uploaded_file = st.file_uploader("Prends ou choisis une photo", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Image choisie", use_column_width=True)

        # Simulation identification
        nom = st.text_input("Nom de la plante (simulation)")
        vertus = st.text_area("Vertus médicinales ou utilisations")
        coords = st.text_input("Coordonnées GPS (optionnel)")

        if st.button("📌 Archiver cette plante"):
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            encoded_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

            new_entry = {
                "nom": nom if nom else "Plante inconnue",
                "date": datetime.now().isoformat(),
                "image": encoded_image,
                "coords": coords,
                "vertus": vertus
            }

            st.session_state.archives.append(new_entry)
            with open(ARCHIVES_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.archives, f, ensure_ascii=False, indent=2)

            st.success("🌱 Plante archivée avec succès !")


















































