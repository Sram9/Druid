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

# --- Initialisation session_state ---
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
    term = st.text_input("🔎 Mot-clé dans vertus")
    if term:
        results = [p for p in archives if term.lower() in p.get("vertus",""").lower()]
        if results:
            for p in results:
                st.write(f"🌿 **{p['nom']}** - {p['date'][:10]}")
                st.write(p.get("vertus","Aucune info"))
        else:
            st.write("Aucun résultat pour ce mot-clé.")
    st.stop()

# --- Archives page ---
if st.session_state.page == "archives":
    st.title("📚 Plantes archivées")
    tri = st.radio("Trier par:", ["Nom","Date"])
    sorted_arch = sorted(archives, key=lambda x: x["nom"] if tri=="Nom" else x["date"])
    for i,p in enumerate(sorted_arch):
        with st.expander(f"{p['nom']} ({p['date'][:10]})"):
            st.write(f"📅 {p['date']}")
            c1,c2,c3 = st.columns(3)
            if c1.button("📍 Localiser",key=f"loc{i}"):
                st.session_state.selected_coords = p.get("coords")
                st.session_state.selected_name = p['nom']
                st.session_state.show_map = True
            if c2.button("🔍 Vertus",key=f"virt{i}"):
                st.markdown(f"**Vertus de {p['nom']}**")
                st.write(p.get("vertus","Aucune info"))
            if c3.button("❌ Supprimer",key=f"del{i}"):
                archives.remove(p)
                with open(ARCHIVES_PATH,'w',encoding='utf-8') as f: json.dump(archives,f,ensure_ascii=False,indent=2)
                st.experimental_rerun()
            new = st.text_input("✏️ Renommer",value=p['nom'],key=f"rn{i}")
            if st.button("💾 Enregistrer nom",key=f"sv{i}"):
                p['nom']=new
                with open(ARCHIVES_PATH,'w',encoding='utf-8') as f: json.dump(archives,f,ensure_ascii=False,indent=2)
                st.success("Nom mis à jour")
    if st.session_state.show_map:
        st.map(pd.DataFrame([
            {"lat":float(pt.split(",")[0]),"lon":float(pt.split(",")[1])} 
            for pt in [st.session_state.selected_coords] if pt
        ]))
        st.markdown(f"[🧭 Navigation](https://www.google.com/maps/dir/?api=1&destination={st.session_state.selected_coords})")
        if st.button("🔙 Retour"):
            st.session_state.show_map=False
            st.experimental_rerun()
    st.stop()

# --- Home page: identification ---
st.title("📷🌿 Identifier une plante")
up=st.file_uploader("Photo",type=["jpg","png","jpeg"]);
if up:
    img=Image.open(up)
    st.image(img,use_container_width=True)
    b=up.read()
    # PlantNet
    try:
        r=requests.post(f"https://my-api.plantnet.org/v2/identify/all?api-key={PLANTNET_API_KEY}",
                        files={"images":(up.name,io.BytesIO(b),mimetypes.guess_type(up.name)[0] or 'image/jpeg')},
                        data={"organs":"leaf"},timeout=10)
        r.raise_for_status();d=r.json();
        top=d["results"][:3]
        st.success("Résultats PlantNet:")
        for x in top: st.write(f"- {x['species']['scientificNameWithoutAuthor']} ({x['score']*100:.1f}%)")
        nm=top[0]['species']['scientificNameWithoutAuthor']
    except:
        st.warning("PlantNet failed, using Plant.id")
        h={"Api-Key":PLANTID_API_KEY}
        r2=requests.post("https://api.plant.id/v2/identify",headers=h,files={"images":b},timeout=15);r2.raise_for_status();p=r2.json()["suggestions"][0]
        nm=p['plant_name']
        st.success(f"Plant.id: {nm} ({p['probability']*100:.1f}%)")
    st.session_state.plant_name=nm
    # Vertus
    if nm in cache: v=cache[nm]
    else:
        now=datetime.utcnow();st.session_state.mistral_calls=[t for t in st.session_state.mistral_calls if now-t<timedelta(60)]
        if len(st.session_state.mistral_calls)<3:
            body={"model":"mistral-tiny","messages":[{"role":"user","content":f"Nom {nm}. Comestible? Vertus?"}],"max_tokens":200}
            h2={"Authorization":f"Bearer {MISTRAL_API_KEY}","Content-Type":"application/json"}
            res=requests.post("https://api.mistral.ai/v1/chat/completions",headers=h2,json=body,timeout=15).json()
            v=res['choices'][0]['message']['content'];cache[nm]=v;open(CACHE_PATH,'w',encoding='utf-8').write(json.dumps(cache,ensure_ascii=False,indent=2))
        else: v="(limite atteinte)"
    st.markdown(f"### Vertus de {nm}");st.write(v)
    if st.button("✅ Archiver cette plante"):
        # GPS prompt
        gps_js="""<script>navigator.geolocation.getCurrentPosition(pos=>{const c=pos.coords.latitude+','+pos.coords.longitude;const i=window.parent.document.querySelector('input[data-testid="stSessionState.coords"]');i&&(i.value=c,i.dispatchEvent(new Event('input',{bubbles:!0})));});</script>"""
        st.components.v1.html(gps_js)
        archives.append({"nom":nm,"date":datetime.now().isoformat(),"coords":st.session_state.coords,"vertus":v})
        open(ARCHIVES_PATH,'w',encoding='utf-8').write(json.dumps(archives,ensure_ascii=False,indent=2))
        st.success("Plante archivée !")
'''

# Write file
file_path = os.path.join(project_dir, 'app.py.txt')
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(app_py_content)

# Create archives.json and cache_virtues.json
open(os.path.join(project_dir,'archives.json'), 'w').close()
open(os.path.join(project_dir,'cache_virtues.json'), 'w').close()

# Zip folder
zip_path = '/mnt/data/Plante_Id_Ai_App.zip'
with zipfile.ZipFile(zip_path, 'w') as zf:
    for fname in ['app.py.txt','archives.json','cache_virtues.json']:
        zf.write(os.path.join(project_dir,fname), arcname=fname)

zip_path














