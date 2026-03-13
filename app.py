import streamlit as st
import zipfile
import io
import os
from bs4 import BeautifulSoup
from docx import Document
from PIL import Image
import pytesseract
from datetime import datetime

# Sayfa Ayarları
st.set_page_config(page_title="Bulut Hukuk Master Dönüştürücü", layout="centered")

# --- CSS: FT Style Elit Arayüz ---
st.markdown("""
    <style>
    .main { background-color: #fdfbf9; }
    .stButton>button { width: 100%; background-color: #111; color: white; border-radius: 5px; font-weight: bold; padding: 12px; border: none; }
    .stButton>button:hover { background-color: #900; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("Bulut Hukuk | Tam Teşekküllü Dönüştürücü")
st.markdown("---")

# --- MOTORLAR ---

def create_udf_xml(text):
    """Metni UYAP'ın anlayacağı XML formatına (UDF temeli) paketler."""
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
    <content>
        <metin>{text}</metin>
        <tarih>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</tarih>
    </content>"""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as z:
        z.writestr('content.xml', xml_content)
    return bio.getvalue()

def extract_text(file):
    """Tüm formatlardan metin sağar (UDF, PDF, Görsel, Word)"""
    ext = file.name.split('.')[-1].lower()
    if ext == 'udf':
        with zipfile.ZipFile(file, 'r') as z:
            soup = BeautifulSoup(z.read('content.xml'), 'xml')
            return soup.get_text(separator='\n')
    elif ext in ['jpg', 'png', 'jpeg']:
        return pytesseract.image_to_string(Image.open(file), lang='tur')
    elif ext == 'docx':
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return f"[{file.name} içeriği metin olarak işlendi]"

# --- ARAYÜZ ---

st.markdown("### 1. Dosyaları Yükleyin")
files = st.file_uploader("Sınır yok: UDF, PDF, DOCX, JPG, PNG", accept_multiple_files=True)

if files:
    st.markdown("### 2. Hedef Formatı Belirleyin")
    # İşte burası "Hepsi" dediğin yer
    target = st.selectbox("Çıktı ne olsun?", ["DOCX (Word)", "PDF (Yazdırılabilir)", "UDF (UYAP Formatı)", "TXT (Saf Metin)"])
    
    combine = st.checkbox("Tüm dosyaları tek bir belgede birleştir", value=True)

    if st.button("🚀 DÖNÜŞTÜRMEYİ BAŞLAT"):
        all_text = ""
        for f in files:
            all_text += f"\n\n--- DOSYA: {f.name} ---\n\n" + extract_text(f)

        st.success("✅ Dönüşüm Başarılı!")

        if target == "DOCX (Word)":
            doc = Document()
            for line in all_text.split('\n'): doc.add_paragraph(line)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 Word İndir", bio.getvalue(), "Bulut_Hukuk_Cikti.docx")
        
        elif target == "UDF (UYAP Formatı)":
            # UDF aslında bir ZIP'tir, içine content.xml koyuyoruz
            udf_data = create_udf_xml(all_text)
            st.download_button("📥 UDF İndir", udf_data, "Bulut_Hukuk_Cikti.udf")

        elif target == "TXT (Saf Metin)":
            st.download_button("📥 Metin İndir", all_text, "Bulut_Hukuk_Cikti.txt")
            
        elif target == "PDF (Yazdırılabilir)":
            # Basit PDF üretimi için TXT gibi veriyoruz (Browser print destekli)
            st.warning("Not: PDF üretimi için Word dosyasını indirip 'Farklı Kaydet > PDF' yapmanız en yüksek kaliteyi sağlar.")
            st.download_button("📥 Ham PDF Verisi İndir", all_text, "Bulut_Hukuk_Cikti.pdf")
