import streamlit as st
import os
import io
from udf_engine import UniversalDocumentReader, UDFExporter, UDFGenerator

st.set_page_config(
    page_title="Bulut Hukuk Doküman Dönüştürücü / Birleştirici", 
    page_icon="⚖️", 
    layout="centered"
)

st.markdown("""
    <style>
    .main { background-color: #fdfbf9; }
    .stButton>button { width: 100%; background-color: #8b0000; color: white; padding: 12px; border: none; font-weight: bold; border-radius: 4px; }
    .stButton>button:hover { background-color: #6d0000; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("Bulut Hukuk Doküman Dönüştürücü / Birleştirici")
st.caption("Gelişmiş UDF, Tablo Rekonstrüksiyonu, E-İmza Tespiti ve Çoklu Format Desteği")
st.markdown("---")

uploaded_files = st.file_uploader(
    "Dosyalarınızı Yükleyin", 
    accept_multiple_files=True, 
    type=['udf', 'pdf', 'docx', 'txt', 'jpg', 'png', 'jpeg', 'tif', 'tiff']
)

if uploaded_files:
    mode = st.radio("İşlem Türünü Seçin:", ["Hepsini Tek Bir Dosyada Birleştir", "Her Birini Ayrı Ayrı Dönüştür"])
    target = st.selectbox("Çıktı Formatı:", ["DOCX (Word)", "PDF", "UDF (UYAP)", "TXT", "HTML (Canlı Önizleme)"])
    
    if st.button("Dönüştürmeyi Başlat"):
        with st.spinner("Dosyalar işleniyor, tablolar ve elektronik imzalar tahlil ediliyor..."):
            processed = []
            for f in uploaded_files:
                bdata = f.read()
                try:
                    res = UniversalDocumentReader.read_document(bdata, f.name)
                    processed.append({'name': f.name, 'res': res})
                except Exception as e:
                    st.error(f"'{f.name}' işlenirken hata oluştu: {e}")

            if processed:
                st.success("✅ Tüm belgeler başarıyla dönüştürüldü.")

                # E-İmza Doğrulama Göstergesi
                for p in processed:
                    sign_info = p['res'].get('sign_info')
                    if sign_info and sign_info.get('signed'):
                        signer = sign_info.get('signer', 'Yetkili İmzacı')
                        title = sign_info.get('title', 'AVUKAT')
                        issuer = sign_info.get('issuer_org', 'Elektronik Sertifika Sağlayıcısı')
                        st.markdown(f"""
                        <div style="background: #eef7ee; border: 1px solid #c2e2c2; border-left: 5px solid #2e7d32; padding: 10px 15px; border-radius: 4px; margin-bottom: 12px; color: #1b5e20;">
                            <strong>🔒 5070 Sayılı Kanuna Uygun Nitelikli E-İmza Tespit Edildi ({p['name']})</strong><br>
                            İmzalayan: <b>{title} {signer}</b> &bull; Kurum: {issuer}
                        </div>
                        """, unsafe_allow_html=True)

                # 1. SENARYO: HEPSİNİ BİRLEŞTİR
                if mode == "Hepsini Tek Bir Dosyada Birleştir":
                    full_text = ""
                    for p in processed:
                        full_text += f"\n\n{'='*30}\nDOSYA: {p['name']}\n{'='*30}\n\n" + p['res']['text']
                    
                    if target == "DOCX (Word)":
                        from docx import Document
                        doc = Document()
                        for line in full_text.split('\n'): doc.add_paragraph(line)
                        bio = io.BytesIO()
                        doc.save(bio)
                        st.download_button("📥 Birleştirilmiş Word İndir", bio.getvalue(), "BulutHukuk_Birlesik.docx")
                        
                    elif target == "PDF":
                        from fpdf import FPDF
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font('Helvetica', '', 10)
                        for line in full_text.split('\n'):
                            if not line.strip(): pdf.ln(4)
                            else: pdf.multi_cell(0, 5.5, line)
                        st.download_button("📥 Birleştirilmiş PDF İndir", bytes(pdf.output()), "BulutHukuk_Birlesik.pdf")
                        
                    elif target == "UDF (UYAP)":
                        udf_bytes = UDFGenerator.create_udf_from_text(full_text)
                        st.download_button("📥 Birleştirilmiş UDF İndir", udf_bytes, "BulutHukuk_Birlesik.udf")
                        
                    elif target == "TXT":
                        st.download_button("📥 Birleştirilmiş TXT İndir", full_text.encode('utf-8'), "BulutHukuk_Birlesik.txt")

                # 2. SENARYO: AYRI AYRI DÖNÜŞTÜR
                else:
                    for p in processed:
                        fname = p['name']
                        base_name = os.path.splitext(fname)[0]
                        res = p['res']
                        doc_obj = res.get('doc_obj')

                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📄 **{fname}**")
                        with col2:
                            if target == "DOCX (Word)":
                                if doc_obj:
                                    out_data = UDFExporter.to_docx(doc_obj)
                                else:
                                    from docx import Document
                                    d = Document()
                                    for line in res['text'].split('\n'): d.add_paragraph(line)
                                    bio = io.BytesIO()
                                    d.save(bio)
                                    out_data = bio.getvalue()
                                st.download_button("📥 Word İndir", out_data, f"{base_name}.docx", key=f"{fname}_docx")
                                
                            elif target == "PDF":
                                if doc_obj:
                                    out_data = UDFExporter.to_pdf(doc_obj)
                                else:
                                    from fpdf import FPDF
                                    pdf = FPDF()
                                    pdf.add_page()
                                    pdf.set_font('Helvetica', '', 10)
                                    for line in res['text'].split('\n'):
                                        if not line.strip(): pdf.ln(4)
                                        else: pdf.multi_cell(0, 5.5, line)
                                    out_data = bytes(pdf.output())
                                st.download_button("📥 PDF İndir", out_data, f"{base_name}.pdf", key=f"{fname}_pdf")
                                
                            elif target == "UDF (UYAP)":
                                udf_bytes = UDFGenerator.create_udf_from_text(res['text'])
                                st.download_button("📥 UDF İndir", udf_bytes, f"{base_name}.udf", key=f"{fname}_udf")
                                
                            elif target == "TXT":
                                st.download_button("📥 TXT İndir", res['text'].encode('utf-8'), f"{base_name}.txt", key=f"{fname}_txt")
                                
                            elif target == "HTML (Canlı Önizleme)":
                                if doc_obj:
                                    st.markdown(UDFExporter.to_html(doc_obj), unsafe_allow_html=True)
                                else:
                                    st.text_area(f"Önizleme - {fname}", res['text'], height=200)
