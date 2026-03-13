import streamlit as st
import zipfile
import io
import os
import urllib.request
from bs4 import BeautifulSoup
from docx import Document
from PIL import Image, ImageSequence
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Sayfa Ayarları ve İsimlendirme (Sıkı Talimatlara Uygun)
st.set_page_config(page_title="Bulut Hukuk Doküman Dönüştürücü / Birleştirici", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #fdfbf9; }
    .stButton>button { width: 100%; background-color: #111; color: white; padding: 12px; border: none; }
    </style>
    """, unsafe_allow_html=True)

st.title("Bulut Hukuk Doküman Dönüştürücü / Birleştirici")
st.markdown("---")

# --- TÜRKÇE FONT YÜKLEME (Siyah Kare Sorununu Çözer) ---
@st.cache_resource
def load_turkish_font():
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
        urllib.request.urlretrieve(url, font_path)
    pdfmetrics.registerFont(TTFont('Roboto', font_path))
    return 'Roboto'

font_name = load_turkish_font()

# --- PDF ÜRETİCİ ---
def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Boş satırları ve gereksiz boşlukları düzelt
    lines = [line.strip() for line in text.split('\n')]
    
    y = height - 50
    c.setFont(font_name, 11) # Türkçe fontu kullan
    
    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont(font_name, 11)
        
        # Çok uzun satırları PDF dışına taşmasın diye bölme işlemi
        if len(line) > 90:
            words = line.split(' ')
            temp_line = ""
            for word in words:
                if len(temp_line) + len(word) < 90:
                    temp_line += word + " "
                else:
                    c.drawString(50, y, temp_line)
                    y -= 15
                    temp_line = word + " "
                    if y < 50:
                        c.showPage()
                        y = height - 50
                        c.setFont(font_name, 11)
            if temp_line:
                c.drawString(50, y, temp_line)
                y -= 15
        else:
            c.drawString(50, y, line)
            y -= 15
            
    c.save()
    return buffer.getvalue()

# --- METİN ÇIKARMA MOTORU ---
def extract_text(file):
    ext = file.name.split('.')[-1].lower()
    
    if ext == 'udf':
        try:
            with zipfile.ZipFile(file, 'r') as z:
                soup = BeautifulSoup(z.read('content.xml'), 'xml')
                return soup.get_text(separator='\n')
        except: return "[UDF Okunamadı]"
        
    elif ext in ['jpg', 'png', 'jpeg']:
        return pytesseract.image_to_string(Image.open(file), lang='tur')
        
    elif ext in ['tif', 'tiff']: # TIFF ve Çok Sayfalı TIFF Desteği
        img = Image.open(file)
        text = ""
        for i, page in enumerate(ImageSequence.Iterator(img)):
            text += f"\n--- Sayfa {i+1} ---\n"
            text += pytesseract.image_to_string(page, lang='tur')
        return text
        
    elif ext == 'docx':
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
        
    return f"[{file.name} formatı için metin çıkarımı yapılamadı]"

# --- ARAYÜZ ---
uploaded_files = st.file_uploader("Dosyalarınızı Yükleyin", accept_multiple_files=True, type=['udf', 'pdf', 'docx', 'jpg', 'png', 'jpeg', 'tif', 'tiff'])

if uploaded_files:
    mode = st.radio("İşlem Türünü Seçin:", ["Hepsini Tek Bir Dosyada Birleştir", "Her Birini Ayrı Ayrı Dönüştür"])
    target = st.selectbox("Çıktı Formatı:", ["DOCX (Word)", "PDF", "UDF (UYAP)", "TXT"])
    
    if st.button("Dönüştürmeyi Başlat"):
        with st.spinner("Dosyalar işleniyor..."):
            
            # 1. SENARYO: HEPSİNİ BİRLEŞTİR
            if mode == "Hepsini Tek Bir Dosyada Birleştir":
                full_text = ""
                for f in uploaded_files:
                    full_text += f"\n\n{'='*20}\nDOSYA: {f.name}\n{'='*20}\n\n" + extract_text(f)
                
                st.success("✅ Tüm dosyalar birleştirildi ve dönüştürüldü.")
                
                if target == "DOCX (Word)":
                    doc = Document()
                    for line in full_text.split('\n'): doc.add_paragraph(line)
                    bio = io.BytesIO()
                    doc.save(bio)
                    st.download_button("📥 Birleştirilmiş Word İndir", bio.getvalue(), "BulutHukuk_Birlesik.docx")
                    
                elif target == "PDF":
                    pdf_data = create_pdf(full_text)
                    st.download_button("📥 Birleştirilmiş PDF İndir", pdf_data, "BulutHukuk_Birlesik.pdf")
                    
                elif target == "UDF (UYAP)":
                    bio = io.BytesIO()
                    with zipfile.ZipFile(bio, 'w') as z:
                        z.writestr('content.xml', f'<?xml version="1.0" encoding="UTF-8"?><content><metin>{full_text}</metin></content>')
                    st.download_button("📥 Birleştirilmiş UDF İndir", bio.getvalue(), "BulutHukuk_Birlesik.udf")
                    
                else:
                    st.download_button("📥 Birleştirilmiş TXT İndir", full_text, "BulutHukuk_Birlesik.txt")

            # 2. SENARYO: AYRI AYRI DÖNÜŞTÜR
            else:
                st.success("✅ Dosyalar ayrı ayrı dönüştürüldü. Aşağıdan indirebilirsiniz:")
                for f in uploaded_files:
                    file_text = extract_text(f)
                    base_name = f.name.rsplit('.', 1)[0]
                    
                    if target == "DOCX (Word)":
                        doc = Document()
                        for line in file_text.split('\n'): doc.add_paragraph(line)
                        bio = io.BytesIO()
                        doc.save(bio)
                        st.download_button(f"📥 {base_name}.docx İndir", bio.getvalue(), f"{base_name}_Cikti.docx", key=f.name+"docx")
                        
                    elif target == "PDF":
                        pdf_data = create_pdf(file_text)
                        st.download_button(f"📥 {base_name}.pdf İndir", pdf_data, f"{base_name}_Cikti.pdf", key=f.name+"pdf")
                        
                    elif target == "UDF (UYAP)":
                        bio = io.BytesIO()
                        with zipfile.ZipFile(bio, 'w') as z:
                            z.writestr('content.xml', f'<?xml version="1.0" encoding="UTF-8"?><content><metin>{file_text}</metin></content>')
                        st.download_button(f"📥 {base_name}.udf İndir", bio.getvalue(), f"{base_name}_Cikti.udf", key=f.name+"udf")
                        
                    else:
                        st.download_button(f"📥 {base_name}.txt İndir", file_text, f"{base_name}_Cikti.txt", key=f.name+"txt")
