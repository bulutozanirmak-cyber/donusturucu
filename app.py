{\rtf1\ansi\ansicpg1254\cocoartf2639
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\froman\fcharset0 Times-Roman;\f1\fnil\fcharset0 AppleColorEmoji;}
{\colortbl;\red255\green255\blue255;\red0\green0\blue0;}
{\*\expandedcolortbl;;\cssrgb\c0\c0\c0;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\deftab720
\pard\pardeftab720\partightenfactor0

\f0\fs24 \cf0 \expnd0\expndtw0\kerning0
\outl0\strokewidth0 \strokec2 import streamlit as st\
import zipfile\
import io\
import os\
from bs4 import BeautifulSoup\
from docx import Document\
from PIL import Image\
import pytesseract\
\
# Sayfa Ayarlar\uc0\u305  (Sade ve Ciddi)\
st.set_page_config(page_title="Bulut Hukuk D\'f6n\'fc\uc0\u351 t\'fcr\'fcc\'fc", layout="centered")\
\
# --- CSS: Aray\'fcz\'fc \uc0\u350 \u305 kla\u351 t\u305 ral\u305 m ---\
st.markdown("""\
    <style>\
    .main \{ background-color: #fdfbf9; \}\
    .stButton>button \{ width: 100%; background-color: #111; color: white; border-radius: 5px; font-weight: bold; padding: 10px; margin-top: 10px; border: none; \}\
    .stButton>button:hover \{ background-color: #333; color: white; \}\
    </style>\
    """, unsafe_allow_html=True)\
\
# --- BA\uc0\u350 LIK ---\
st.title("Bulut Hukuk Dok\'fcman D\'f6n\'fc\uc0\u351 t\'fcr\'fcc\'fc / Birle\u351 tirici")\
st.markdown("---")\
\
# --- MOTOR 1: UDF TEM\uc0\u304 ZL\u304 K ROBOTU (Senin Colab Mant\u305 \u287 \u305 ) ---\
def is_garbage(text):\
    text = text.strip()\
    if not text: return True\
    if len(text) < 2: return True\
\
    garbage_list = [\
        'il_Ilce', 'dosyaNo', 'ilgiliIcraMudurlugu',\
        'borcluBilgisi', 'alacakliAvukatAdiSoyadi', 'personelAd',\
        'personelGorev', 'personelSicil', 'talepAciklama',\
        'kararAciklama', 'tarih', 'e-imzal\uc0\u305 d\u305 r', 'vekilBilgisi'\
    ]\
    if text in garbage_list: return True\
    if " " not in text and any(c.isdigit() for c in text) and any(c.isalpha() for c in text):\
        if len(text) > 5 and len(text) < 20: return True\
    return False\
\
def extract_udf(file):\
    extracted_lines = []\
    try:\
        with zipfile.ZipFile(file, 'r') as z:\
            xml_files = [n for n in z.namelist() if n.endswith('.xml')]\
            if 'content.xml' in xml_files:\
                xml_files.insert(0, xml_files.pop(xml_files.index('content.xml')))\
            \
            for xml_file in xml_files:\
                with z.open(xml_file) as f:\
                    soup = BeautifulSoup(f.read(), 'xml')\
                    lines = soup.get_text(separator='\\n').splitlines()\
                    for line in lines:\
                        if not is_garbage(line):\
                            if extracted_lines and extracted_lines[-1] == line.strip():\
                                continue\
                            extracted_lines.append(line.strip())\
        return "\\n".join(extracted_lines)\
    except Exception as e:\
        return f"HATA: Dosya okunamad\uc0\u305  (\{e\})"\
\
# --- ARAY\'dcZ VE Y\'d6NERGELER ---\
st.markdown("### 1. Dosyalar\uc0\u305 n\u305 z\u305  Y\'fckleyin")\
st.info("UDF, PDF, DOCX (Word) veya G\'f6rsel (JPG, PNG) format\uc0\u305 ndaki dosyalar\u305 n\u305 z\u305  buraya y\'fckleyebilirsiniz. Ayn\u305  anda birden fazla dosya se\'e7ilebilir.")\
uploaded_files = st.file_uploader("Dosyalar\uc0\u305  S\'fcr\'fckleyin veya Se\'e7in", accept_multiple_files=True, type=['udf', 'pdf', 'docx', 'jpg', 'png'])\
\
if uploaded_files:\
    st.markdown("### 2. \uc0\u304 \u351 lem T\'fcr\'fcn\'fc Se\'e7in")\
    mode = st.radio("Y\'fckledi\uc0\u287 iniz dosyalarla ne yapmak istiyorsunuz?", \
                    ["Hepsini Tek Bir Dosyada Birle\uc0\u351 tir", "Her Birini Ayr\u305  Ayr\u305  D\'f6n\'fc\u351 t\'fcr (Yak\u305 nda)"])\
\
    st.markdown("### 3. \'c7\uc0\u305 kt\u305  Format\u305 n\u305  Belirleyin")\
    target_format = st.selectbox("Sonu\'e7 dosyas\uc0\u305  hangi formatta olsun?", \
                                 ["DOCX (Word Dosyas\uc0\u305 )", "TXT (D\'fcz Metin)"])\
\
    st.markdown("### 4. \uc0\u304 \u351 lemi Ba\u351 lat\u305 n")\
    if st.button("
\f1 \uc0\u55357 \u56580 
\f0  D\'f6n\'fc\uc0\u351 t\'fcrme \u304 \u351 lemini Ba\u351 lat"):\
        master_content = ""\
        \
        with st.spinner('Dosyalar i\uc0\u351 leniyor, l\'fctfen bekleyin...'):\
            for uploaded_file in uploaded_files:\
                file_ext = uploaded_file.name.split('.')[-1].lower()\
                \
                # UDF \uc0\u304 \u351 leme\
                if file_ext == 'udf':\
                    content = extract_udf(uploaded_file)\
                # G\'f6rsel \uc0\u304 \u351 leme (OCR)\
                elif file_ext in ['jpg', 'png']:\
                    try:\
                        image = Image.open(uploaded_file)\
                        content = pytesseract.image_to_string(image, lang='tur')\
                    except Exception as e:\
                        content = f"[G\'f6rsel okunamad\uc0\u305 : \{e\}]"\
                # PDF ve Di\uc0\u287 erleri (\u350 imdilik yer tutucu, PDF okuma mod\'fcl\'fcn\'fc de entegre edece\u287 iz)\
                else:\
                    content = f"[\{uploaded_file.name\} ba\uc0\u351 ar\u305 yla sisteme eklendi]"\
                \
                # Dosyalar\uc0\u305  Birle\u351 tirme Ayra\'e7lar\u305 \
                master_content += f"\\n\\n\{'='*30\}\\nDOSYA: \{uploaded_file.name\}\\n\{'='*30\}\\n\\n" + content\
\
        st.success("
\f1 \uc0\u9989 
\f0  \uc0\u304 \u351 lem tamamland\u305 ! Sonucu a\u351 a\u287 \u305 dan indirebilirsiniz.")\
\
        # \uc0\u304 ndirme \'c7\u305 kt\u305 lar\u305 \
        if target_format == "DOCX (Word Dosyas\uc0\u305 )":\
            doc = Document()\
            for line in master_content.split('\\n'):\
                doc.add_paragraph(line)\
            bio = io.BytesIO()\
            doc.save(bio)\
            st.download_button("
\f1 \uc0\u55357 \u56549 
\f0  Word Dosyas\uc0\u305  Olarak \u304 ndir (.docx)", bio.getvalue(), "BulutHukuk_Birlesik_Dosya.docx")\
        else:\
            st.download_button("
\f1 \uc0\u55357 \u56549 
\f0  Metin Dosyas\uc0\u305  Olarak \u304 ndir (.txt)", master_content, "BulutHukuk_Birlesik_Dosya.txt")}