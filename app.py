import streamlit as st
import base64
import requests
import json
from io import BytesIO
from PIL import Image
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# Initialisation de l'état de session
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "coords" not in st.session_state:
    st.session_state.coords = None
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "result" not in st.session_state:
    st.session_state.result = None
if "page" not in st.session_state:
    st.session_state.page = "main"
if "selected_plant" not in st.session_state:
    st.session_state.selected_plant = None

# Fonctions

def save_to_archive(user_id, lat, lon, image_data, result):
    archive_entry = {
        "user": user_id,
        "lat": lat,
        "lon": lon,
        "image": image_data,
        "result": result,
    }
    with open("archive.json", "a") as f:
        f.write(json.dumps(archive_entry) + "\n")

def plantnet_identify(image_bytes):
    url = "https://my-api.plantnet.org/v2/identify/all"
    files = {"images": ("plant.jpg", image_bytes)}
    data = {"organs": ["leaf"]}
    params = {"api-key": st.secrets["PLANTNET_API_KEY"]}
    response = requests.post(url, files=files, data=data, params=params)
    return response.json()

def plantid_identify(image_bytes):
    headers = {"Content-Type": "application/json"}
    img_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "images": [img_b64],
        "latitude": st.session_state.coords["lat"] if st.session_state.coords else None,
        "longitude": st.session_state.coords["lon"] if st.session_state.coords else None,
        "similar_images": True,
    }
    
    if "PLANT_ID_API_KEY" not in st.secrets:
        st.warning("La clé API Plant.id est manquante, veuillez vérifier vos secrets.")
        return None
    
    response = requests.post(
        "https://plant.id/api/v3/identification",
        headers=headers,
        params={"apikey": st.secrets["PLANT_ID_API_KEY"]},
        json=payload,
    )
    return response.json()

def mistral_query(plant_name):
    prompt = f"Cette plante s'appelle {plant_name}. Cette plante est-elle comestible ou a-t-elle des vertus médicinales et, si oui, comment est-elle utilisée ?"
    headers = {
        "Authorization": f"Bearer {st.secrets['MISTRAL_API_KEY']}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers=headers,
        json={
            "model": "mistral-small",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return response.json()["choices"][0]["message"]["content"]

# Interface
st.title("📷🌿 Identifier une plante + vertus")

st.sidebar.title("Navigation")
st.session_state.page = st.sidebar.radio("Aller à", ["nouvelle identification", "archives", "carte"])

if st.session_state.page == "nouvelle identification":
    st.text_input("👤 Identifiant utilisateur", key="user_id")

    if st.session_state.coords is None:
        coords = get_geolocation()
        if coords and coords["latitude"]:
            st.session_state.coords = {"lat": coords["latitude"], "lon": coords["longitude"]}

    up = st.file_uploader("Téléversez une image de plante", type=["jpg", "jpeg", "png"])
    if up:
        image = Image.open(up)
        st.image(image, caption="Image téléversée", use_container_width=True)
        st.session_state.uploaded_image = image

        image_bytes = BytesIO()
        image.save(image_bytes, format="JPEG")
        image_bytes = image_bytes.getvalue()

        with st.spinner("Identification via PlantNet..."):
            plantnet_res = plantnet_identify(image_bytes)

        with st.spinner("Identification via Plant.id..."):
            plantid_res = plantid_identify(image_bytes)

        nom = plantnet_res.get("results", [{}])[0].get("species", {}).get("scientificNameWithoutAuthor")
        if not nom and plantid_res:
            nom = plantid_res.get("suggestions", [{}])[0].get("plant_name")

        st.success(f"🌱 Plante identifiée : {nom}")

        # Affichage des résultats de PlantNet avec les trois premières propositions et pourcentages
        if plantnet_res.get("results"):
            st.markdown("### Résultats de l'identification PlantNet :")
            selected_plant = None
            for i, result in enumerate(plantnet_res["results"][:3]):
                species = result.get("species", {})
                scientific_name = species.get("scientificNameWithoutAuthor", "Nom scientifique non trouvé")
                score = result.get("score", 0) * 100  # Pourcentage de confiance
                if st.button(f"Proposition {i + 1}: {scientific_name} ({score:.2f}%)"):
                    selected_plant = scientific_name
                    st.session_state.selected_plant = scientific_name  # Enregistrer l'option choisie

            # Si une plante est sélectionnée, on lance Mistral
            if selected_plant or st.session_state.get("selected_plant"):
                plant_to_query = selected_plant or st.session_state.selected_plant
                with st.spinner(f"Recherche des vertus avec Mistral pour {plant_to_query}..."):
                    vertus = mistral_query(plant_to_query)

                st.markdown("### 🧪 Vertus ou usages")
                st.write(vertus)
                st.session_state.result = {"nom": plant_to_query, "vertus": vertus}

                # Afficher les résultats de PlantNet et Mistral pour la plante sélectionnée
                st.markdown(f"### 🌱 Plante sélectionnée : {plant_to_query}")
                st.markdown(f"Confiance : {score:.2f}%")
                st.markdown(f"Vertus ou usages : {vertus}")

            # Sinon, afficher la réponse automatique pour la première proposition
            elif not st.session_state.get("selected_plant"):
                first_result = plantnet_res["results"][0]
                first_species = first_result.get("species", {})
                first_scientific_name = first_species.get("scientificNameWithoutAuthor", "Nom scientifique non trouvé")
                with st.spinner(f"Recherche des vertus avec Mistral pour {first_scientific_name}..."):
                    vertus = mistral_query(first_scientific_name)

                st.markdown("### 🧪 Vertus ou usages")
                st.write(vertus)
                st.session_state.result = {"nom": first_scientific_name, "vertus": vertus}

        # Sauvegarde
        if st.button("📥 Archiver cette plante"):
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            encoded_image = base64.b64encode(buffered.getvalue()).decode()
            coords = st.session_state.coords or {"lat": None, "lon": None}
            save_to_archive(st.session_state.user_id, coords["lat"], coords["lon"], encoded_image, st.session_state.result)
            st.success("🌿 Plante archivée !")

elif st.session_state.page == "archives":
    st.title("📚 Archives")
    try:
        with open("archive.json") as f:
            lines = f.readlines()
        for line in lines[::-1]:
            item = json.loads(line)
            if item["user"] != st.session_state.user_id:
                continue
            st.image(base64.b64decode(item["image"]), width=150)
            st.markdown(f"**🌱 {item['result']['nom']}**")
            st.markdown(item['result']['vertus'])
            st.markdown("---")
    except FileNotFoundError:
        st.warning("Aucune archive disponible.")

elif st.session_state.page == "carte":
    st.title("🗺️ Carte des plantes archivées")
    import pandas as pd
    import pydeck as pdk

    try:
        with open("archive.json") as f:
            lines = f.readlines()
        data = [json.loads(line) for line in lines if json.loads(line)["user"] == st.session_state.user_id]
        df = pd.DataFrame(data)
        df = df.dropna(subset=["lat", "lon"])
        st.pydeck_chart(pdk.Deck(
            initial_view_state=pdk.ViewState(
                latitude=df["lat"].mean(),
                longitude=df["lon"].mean(),
                zoom=6,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position="[lon, lat]",
                    get_radius=5000,
                    get_color=[0, 200, 0],
                    pickable=True,
                )
            ],
            tooltip={"text": "{result[nom]}"},
        ))
    except Exception as e:
        st.error(f"Erreur lors de l'affichage de la carte : {e}")

















































