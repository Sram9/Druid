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

# --- Chemins des fichiers ---
CACHE_PATH = "cache_virtues.json"
ARCHIVES_PATH = "archives.json"

# --- Charger ou initialiser le cache ---
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

# --- Charger ou initialiser les archives ---
if os.path.exists(ARCHIVES_PATH):
    with open(ARCHIVES_PATH, "r", encoding="utf-8") as f:
        archives = json.load(f)
else:
    archives = []

# --- Session state defaults ---
if "page" not in st.session_state:
    st.session_state.page = "home"
if "coords" not in st.session_state:
    st.session_state.coords = None
if "selected_coords" not in st.session_state:
    st.session_state.selected_coords = None
if "selected_name" not in st.session_state:
    st.session_state.selected_name = None
if "show_map" not in st.session_state:
    st.session_state.show_map = False
if "mistral_calls" not in st.session_state:
    st.session_state.mistral_calls = []

# --- Sidebar menu ---
with st.sidebar:
    st.markdown("## 📚 Menu")
    if st.button(("✅ " if st.session_state.page=="home" else "") + "🌿 Nouvelle identification"):
        st.session_state.page = "home"
    if st.button(("✅ " if st.session_state.page=="archives" else "") + "📚 Archives"):
        st.session_state.page = "archives"
    if st.button(("✅ " if st.session_state.page=="search" else "") + "🔍 Recherche par propriétés"):
        st.session_state.page = "search"

# --- Recherche par propriétés ---
if st.session_state.page == "search":
    st.title("🔍 Recherche par propriétés")
    term = st.text_input("🔎 Mot-clé dans les vertus archives")
    if term:
        results = [p for p in archives if term.lower() in p.get("vertus", "").lower()]
        for p in results:
            st.write(f"🌿 **{p['nom']}** — {p['date'][:10]}")
            st.write(p.get("vertus", "Aucune info"))
    else:
        st.write("Entrez un mot-clé pour filtrer.")

# --- Archives page ---
elif st.session_state.page == "archives":
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par :", ["Nom", "Date"])
    sorted_arch = sorted(archives, key=lambda x: x["nom"] if tri=="Nom" else x["date"])
    for i,p in enumerate(sorted_arch):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(p.get("vertus", "Aucune info"))
            c1,c2,c3 = st.columns(3)
            if c1.button("📍 Localiser", key=f"loc{i}"):
                st.session_state.selected_coords = p.get("coords")
                st.session_state.selected_name = p['nom']
                st.session_state.show_map = True
            if c2.button("❌ Supprimer", key=f"del{i}"):
                archives.remove(p)
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.experimental_rerun()
            new = st.text_input("✏️ Renommer", value=p['nom'], key=f"rn{i}")
            if c3.button("💾", key=f"sv{i}"):
                p['nom'] = new
                with open(ARCHIVES_PATH, "w", encoding="utf-8") as f:
                    json.dump(archives, f, ensure_ascii=False, indent=2)
                st.success("Nom mis à jour")
    if st.session_state.show_map:
        st.map(pd.DataFrame([
            {"lat":float(p['coords'].split(',')[0]),"lon":float(p['coords'].split(',')[1])}
            for p in archives if p.get('coords')
        ]))

# --- Geolocalisation script ---
st.components.v1.html("""
<script>
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    function(pos) {
      const coords = pos.coords.latitude + ',' + pos.coords.longitude;
      const streamlitCoords = window.parent.document.querySelector('input[data-testid="stSessionState.coords"]');
      if (streamlitCoords) {
        streamlitCoords.value = coords;
        streamlitCoords.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
  );
}
</script>
""", height=0)

# --- Identification page ---
else:
    st.title("📷🌿 Identifier une plante")
    file = st.file_uploader("Photo", type=["jpg","png"])
    if file:
        img=Image.open(file)
        st.image(img,use_container_width=True)
        # identification PlantNet
        try:
            r=requests.post(f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                files={"images":(file.name,io.BytesIO(file.read()),mimetypes.guess_type(file.name)[0] or "image/jpeg")},
                data={"organs":"leaf"},timeout=10)
            data=r.json()["results"]
            name=data[0]["species"]["scientificNameWithoutAuthor"]
        except:
            name="Inconnu"
        st.session_state.plant_name=name
        # vertus
        if name in cache:
            v=cache[name]
        else:
            now=datetime.utcnow()
            calls=[t for t in st.session_state.mistral_calls if now-t<timedelta(seconds=60)]
            if len(calls)<3:
                prompt=f"Vertus de {name}? Comestible?";
                h={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
                b={"model":"mistral-tiny","messages":[{"role":"user","content":prompt}],"max_tokens":200}
                res=requests.post("https://api.mistral.ai/v1/chat/completions",headers=h,json=b).json()
                v=res["choices"][0]["message"]["content"]
                cache[name]=v;open(CACHE_PATH,"w").write(json.dumps(cache,ensure_ascii=False,indent=2))
            else: v="Limite atteinte"
        st.write(v)
        # archiver
        if st.button("✅ Archiver"):
            loc=None
            loc = st.session_state.coords
            except: pass
            archives.append({"nom":name,"date":datetime.now().isoformat(),"coords":loc,"vertus":v})
            open(ARCHIVES_PATH,"w").write(json.dumps(archives,ensure_ascii=False,indent=2))
            st.success("Archivée")




















