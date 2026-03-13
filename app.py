import streamlit as st
import zipfile
import io
import os
from bs4 import BeautifulSoup
from docx import Document
from PIL import Image
import pytesseract

# Sayfa Ayarları
st.set_page_config(page_title="Bulut Hukuk Dönüştürücü", layout="centered")

# --- CSS ---
st.markdown("""
    <style>
    .main { background-color: #fdfbf9; }
    .stButton>button { width: 100%; background-color: #111; color: white; border-radius: 5px; font-weight: bold; padding: 10px; margin-top: 10px; border: none; }
    .stButton>button:hover { background-color: #333; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("Bulut Hukuk Doküman Dönüştürücü / Birleştirici")
st.markdown("---")

# --- MOTOR ---
def is_garbage(text):
    text = text.strip()
    if not text or len(text) < 2: return True
    garbage_list = ['il_Ilce', 'dosyaNo', 'ilgiliIcraMudurlugu', 'borcluBilgisi', 'alacakliAvukatAdiSoyadi', 'personelAd', 'personelGorev', 'personelSicil', 'talepAciklama', 'kararAciklama', 'tarih', 'e-imzalıdır', 'vekilBilgisi']
    if text in garbage_list: return True
    return False

def extract_udf(file):
    extracted_lines = []
    try:
        with zipfile.ZipFile(file, 'r') as z:
            xml_files = [n for n in z.namelist() if n.endswith('.xml')]
            if 'content.xml' in xml_files:
                xml_files.insert(0, xml_files.pop(xml_files.index('content.xml')))
            for xml_file in xml_files:
                with z.open(xml_file) as f:
                    soup = BeautifulSoup(f.read(), 'xml')
                    lines = soup.get_text(separator='\n').splitlines()
                    for line in lines:
                        if not is_garbage(line):
                            if extracted_lines and extracted_lines[-1] == line.strip(): continue
                            extracted_lines.append(line.strip())
        return "\n".join(extracted_lines)
    except Exception as e:
        return f"HATA: {e}"

# --- ARAYÜZ ---
st.markdown("### 1. Dosyalarınızı Yükleyin")
uploaded_files = st.file_uploader("UDF, PDF, DOCX, JPG, PNG", accept_multiple_files=True, type=['udf', 'pdf', 'docx', 'jpg', 'png'])

if uploaded_files:
    st.markdown("### 2. İşlem Türü ve Format")
    mode = st.radio("Seçim yapın:", ["Hepsini Tek Bir Dosyada Birleştir", "Ayrı Ayrı Dönüştür"])
    target_format = st.selectbox("Format:", ["DOCX (Word)", "TXT"])

    if st.button("🔄 İşlemi Başlat"):
        master_content = ""
        with st.spinner('İşleniyor...'):
            for uploaded_file in uploaded_files:
                file_ext = uploaded_file.name.split('.')[-1].lower()
                if file_ext == 'udf':
                    content = extract_udf(uploaded_file)
                elif file_ext in ['jpg', 'png']:
                    image = Image.open(uploaded_file)
                    content = pytesseract.image_to_string(image, lang='tur')
                else:
                    content = f"[{uploaded_file.name} eklendi]"
                master_content += f"\n\n{'='*20}\n{uploaded_file.name}\n{'='*20}\n\n" + content

        st.success("✅ Hazır!")
        if target_format == "DOCX (Word)":
            doc = Document()
            for line in master_content.split('\n'): doc.add_paragraph(line)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 Word İndir", bio.getvalue(), "BulutHukuk_Dosya.docx")
        else:
            st.download_button("📥 Metin İndir", master_content, "BulutHukuk_Dosya.txt")
