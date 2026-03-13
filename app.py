import streamlit as st
import zipfile
import io
from bs4 import BeautifulSoup
from docx import Document
from PIL import Image
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Sayfa Ayarları
st.set_page_config(page_title="Bulut Hukuk Master", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #fdfbf9; }
    .stButton>button { width: 100%; background-color: #111; color: white; padding: 12px; border: none; }
    </style>
    """, unsafe_allow_html=True)

st.title("Bulut Hukuk | Nihai Dönüştürücü")

# --- PDF ÜRETİCİ MOTOR ---
def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    lines = text.split('\n')
    
    y = height - 50  # Üst boşluk
    c.setFont("Helvetica", 10) # Standart font (Türkçe karakter desteği için gerekirse TTF yüklenebilir)
    
    for line in lines:
        if y < 50: # Sayfa biterse yeni sayfaya geç
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.drawString(50, y, line)
        y -= 15 # Satır aralığı
        
    c.save()
    return buffer.getvalue()

# --- DİĞER MOTORLAR ---
def extract_text(file):
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
    return f"[{file.name} işlendi]"

# --- ARAYÜZ ---
uploaded_files = st.file_uploader("Dosyaları yükleyin (UDF, PDF, DOCX, JPG, PNG)", accept_multiple_files=True)

if uploaded_files:
    target = st.selectbox("Hedef Format:", ["PDF (Doğrudan)", "DOCX (Word)", "UDF (UYAP)", "TXT"])
    
    if st.button("🚀 İŞLEMİ BAŞLAT"):
        full_text = ""
        for f in uploaded_files:
            full_text += f"\n\n--- DOSYA: {f.name} ---\n" + extract_text(f)
            
        st.success("✅ Dönüşüm tamamlandı.")

        if target == "PDF (Doğrudan)":
            pdf_data = create_pdf(full_text)
            st.download_button("📥 PDF İndir", pdf_data, "BulutHukuk_Cikti.pdf")
        
        elif target == "DOCX (Word)":
            doc = Document()
            for line in full_text.split('\n'): doc.add_paragraph(line)
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("📥 Word İndir", bio.getvalue(), "BulutHukuk_Cikti.docx")
            
        elif target == "UDF (UYAP)":
            # Basit UDF XML yapısı
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, 'w') as z:
                z.writestr('content.xml', f'<?xml version="1.0" encoding="UTF-8"?><content><metin>{full_text}</metin></content>')
            st.download_button("📥 UDF İndir", bio.getvalue(), "BulutHukuk_Cikti.udf")
            
        else:
            st.download_button("📥 TXT İndir", full_text, "BulutHukuk_Cikti.txt")
