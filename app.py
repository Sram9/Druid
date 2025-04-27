import streamlit as st
import requests
import pandas as pd
import json

# Fonction pour gérer la demande d'autorisation de géolocalisation
def demande_permission_gps():
    # Vérification de la permission de géolocalisation
    st.write("Avant de localiser, vous devez activer l'accès à la géolocalisation.")
    if st.button("Activer GPS"):
        gps_js = """
        <script>
            if ("geolocation" in navigator) {
                navigator.geolocation.getCurrentPosition(function(position) {
                    const coords = position.coords.latitude + ',' + position.coords.longitude;
                    const input = window.parent.document.querySelector('input[data-testid="stSessionState.coords"]');
                    if (input) {
                        input.value = coords;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                });
            } else {
                alert("La géolocalisation n'est pas disponible sur ce navigateur.");
            }
        </script>
        """
        st.markdown(gps_js, unsafe_allow_html=True)

# Fonction pour envoyer le prompt modifié à Mistral
def obtenir_virtus_de_plante(plant_name):
    prompt = f"Cette plante est-elle comestible ou a-t-elle des vertus médicinales et, si oui, comment est-elle utilisée ? Réponds pour : {plant_name}."
    
    # Appel à l'API de Mistral (ou à toute autre source pour récupérer la réponse)
    # Remplacez l'URL par celle de votre API ou service
    url_mistral = "https://votre_api_mistral.com/get_response"
    response = requests.post(url_mistral, json={'prompt': prompt})
    data = response.json()
    return data.get("response", "Pas de réponse disponible")

# Fonction pour afficher les plantes archivées
def afficher_plantes():
    st.header("Mes Plantes Archivées")
    
    plantes_archivees = []  # Remplir cette liste avec les plantes archivées depuis votre base de données
    for plante in plantes_archivees:
        # Afficher chaque plante avec le bouton d'archivage
        st.write(plante['nom'])
        st.button("Archiver", key=plante['id'])

# Fonction pour afficher la localisation
def afficher_localisation():
    # Vérifier si la localisation est disponible
    if 'coords' in st.session_state:
        coords = st.session_state['coords']
        latitude, longitude = map(float, coords.split(','))
        st.map(pd.DataFrame([{'lat': latitude, 'lon': longitude}]))
    else:
        st.write("Aucune coordonnée disponible. Veuillez activer votre GPS.")

# Initialisation de l'application
def app():
    # Demander la permission pour activer GPS
    demande_permission_gps()

    # Afficher la localisation et les informations sur les plantes
    afficher_localisation()

    # Afficher les plantes archivées
    afficher_plantes()

    # Lorsque l'utilisateur clique sur archiver, obtenir les informations sur la plante via Mistral
    if st.button("Archiver cette plante"):
        plant_name = "Nom de la plante"  # Remplacer par le nom réel de la plante
        vertus = obtenir_virtus_de_plante(plant_name)
        st.write(f"Vertus de la plante : {vertus}")

# Exécution de l'application
if __name__ == "__main__":
    app()


























