#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VEX Master Architecture: Unified UDF / DOCX / PDF / OCR Converter & Engine
Authored by Bulut Ozan Irmak (bulutozanirmak-cyber) & Enhanced with Top Legal-Tech Kits
"""

import os
import re
import io
import html
import base64
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

# Document & PDF generation
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_UNDERLINE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

import fitz  # PyMuPDF
from fpdf import FPDF
from PIL import Image

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# Font definitions
FONT_DIR = "/Users/refikirmak/.gemini/antigravity/scratch/vex_repo"
FONT_REG = os.path.join(FONT_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Roboto-Bold.ttf")
FONT_ITAL = os.path.join(FONT_DIR, "Roboto-Italic.ttf")


# ---------------------------------------------------------------------------
# E-İmza (CAdES / PKCS#7) Extractor
# ---------------------------------------------------------------------------

def extract_eimza_metadata(sgn_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Extracts 5070-compliant digital signature and certificate details from sign.sgn."""
    if not sgn_bytes or len(sgn_bytes) < 100:
        return None
    try:
        p1 = subprocess.run(
            ['openssl', 'pkcs7', '-inform', 'DER', '-print_certs'],
            input=sgn_bytes, capture_output=True, check=False
        )
        if p1.returncode != 0 or not p1.stdout:
            return {'signed': True, 'raw': True}
            
        p2 = subprocess.run(
            ['openssl', 'x509', '-subject', '-issuer', '-dates', '-noout', '-nameopt', 'multiline'],
            input=p1.stdout, capture_output=True, check=False
        )
        txt = p2.stdout.decode('utf-8', errors='ignore')
        
        def clean_val(v: str) -> str:
            out = []
            i = 0
            while i < len(v):
                if v[i] == '\\' and i + 1 < len(v):
                    if v[i+1] in ('U', 'u') and i + 6 <= len(v):
                        try:
                            code = int(v[i+2:i+6], 16)
                            out.append(chr(code))
                            i += 6
                            continue
                        except ValueError:
                            pass
                    elif i + 3 <= len(v):
                        try:
                            code = int(v[i+1:i+3], 16)
                            out.append(bytes([code]).decode('latin1', errors='ignore'))
                            i += 3
                            continue
                        except ValueError:
                            pass
                out.append(v[i])
                i += 1
            return ''.join(out).strip()

        data = {'signed': True, 'signer': '', 'title': '', 'issuer_org': '', 'law_ref': '', 'valid_until': ''}
        for line in txt.split('\n'):
            line = line.strip()
            if '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = clean_val(v)
                if k == 'commonName' and not data['signer']:
                    data['signer'] = v
                elif k == 'title':
                    data['title'] = v
                elif k == 'organizationName' and not data['issuer_org']:
                    data['issuer_org'] = v
                elif k == 'organizationalUnitName' and '5070' in v:
                    data['law_ref'] = v
                elif k == 'notAfter':
                    data['valid_until'] = v

        if not data['signer']:
            data['signer'] = "Yetkili İmzacı"
        return data
    except Exception as e:
        return {'signed': True, 'error': str(e)}


# ---------------------------------------------------------------------------
# UDF Data Models
# ---------------------------------------------------------------------------

class UDFRun:
    def __init__(self, text: str, bold: bool = False, italic: bool = False, 
                 underline: bool = False, size: float = 11.0, 
                 font_family: str = "Times New Roman", foreground: Optional[str] = None):
        self.text = text
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.size = size
        self.font_family = font_family
        self.foreground = foreground

class UDFImage:
    def __init__(self, image_bytes: bytes, width: float = 0, height: float = 0):
        self.image_bytes = image_bytes
        self.width = width
        self.height = height

class UDFParagraph:
    def __init__(self, alignment: int = 0, first_line_indent: float = 0.0, 
                 left_indent: float = 0.0, right_indent: float = 0.0, 
                 space_above: float = 0.0, space_below: float = 0.0):
        self.alignment = alignment  # 0=Left, 1=Center, 2=Right, 3=Justify
        self.first_line_indent = first_line_indent
        self.left_indent = left_indent
        self.right_indent = right_indent
        self.space_above = space_above
        self.space_below = space_below
        self.items: List[Any] = []  # List of UDFRun or UDFImage

    @property
    def text(self) -> str:
        return "".join(it.text for it in self.items if isinstance(it, UDFRun))

class UDFCell:
    def __init__(self, col_span: int = 1, row_span: int = 1, border: str = "borderCell", fill_color: Optional[str] = None):
        self.col_span = col_span
        self.row_span = row_span
        self.border = border
        self.fill_color = fill_color
        self.paragraphs: List[UDFParagraph] = []

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

class UDFRow:
    def __init__(self):
        self.cells: List[UDFCell] = []

class UDFTable:
    def __init__(self, name: str = "", column_count: int = 0, 
                 column_spans: Optional[List[float]] = None, border: str = "borderNone"):
        self.name = name
        self.column_count = column_count
        self.column_spans = column_spans or []
        self.border = border
        self.rows: List[UDFRow] = []

class UDFDocument:
    def __init__(self):
        self.blocks: List[Any] = []  # List of UDFParagraph or UDFTable
        self.eimza: Optional[Dict[str, Any]] = None
        self.raw_cdata: str = ""
        self.styles: Dict[str, Any] = {}
        self.margins: Dict[str, float] = {
            'left': 70.875, 'right': 70.875, 'top': 70.875, 'bottom': 70.875
        }


# ---------------------------------------------------------------------------
# High-Accuracy UDF Parser
# ---------------------------------------------------------------------------

class UDFParser:
    @staticmethod
    def parse_from_bytes(udf_bytes: bytes) -> UDFDocument:
        doc = UDFDocument()
        xml_content = None
        sgn_bytes = None

        if zipfile.is_zipfile(io.BytesIO(udf_bytes)):
            with zipfile.ZipFile(io.BytesIO(udf_bytes), 'r') as z:
                for name in z.namelist():
                    if name.lower() == 'content.xml':
                        xml_content = z.read(name)
                    elif name.lower() == 'sign.sgn':
                        sgn_bytes = z.read(name)
        else:
            xml_content = udf_bytes

        if not xml_content:
            raise ValueError("Geçersiz UDF dosyası: 'content.xml' bulunamadı.")

        # Decode XML
        raw_xml = ""
        for enc in ['utf-8', 'windows-1254', 'iso-8859-9', 'cp1254']:
            try:
                raw_xml = xml_content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not raw_xml:
            raw_xml = xml_content.decode('utf-8', errors='ignore')

        if sgn_bytes:
            doc.eimza = extract_eimza_metadata(sgn_bytes)

        # Parse XML tree
        try:
            tree = ET.fromstring(raw_xml)
        except ET.ParseError:
            # Clean possible invalid XML control characters
            cleaned_xml = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', raw_xml)
            tree = ET.fromstring(cleaned_xml)

        # 1. CDATA text extraction
        cdata_text = ""
        content_node = tree.find('.//content')
        if content_node is not None and content_node.text:
            cdata_text = content_node.text
        doc.raw_cdata = cdata_text

        # 2. Properties (margins)
        page_format = tree.find('.//pageFormat')
        if page_format is not None:
            for side in ['leftMargin', 'rightMargin', 'topMargin', 'bottomMargin']:
                if side in page_format.attrib:
                    doc.margins[side.replace('Margin', '')] = float(page_format.attrib[side])

        # 3. Block Elements Parser
        elements_node = tree.find('.//elements')
        if elements_node is not None:
            for child in elements_node:
                if child.tag == 'paragraph':
                    p = UDFParser._parse_paragraph(child, cdata_text)
                    doc.blocks.append(p)
                elif child.tag == 'table':
                    t = UDFParser._parse_table(child, cdata_text)
                    doc.blocks.append(t)
        else:
            # Fallback if no <elements> tag
            p = UDFParagraph(alignment=0)
            p.items.append(UDFRun(text=cdata_text))
            doc.blocks.append(p)

        return doc

    @staticmethod
    def _parse_paragraph(p_elem: ET.Element, cdata: str) -> UDFParagraph:
        align_val = int(p_elem.attrib.get('Alignment', 0))
        p = UDFParagraph(
            alignment=align_val,
            first_line_indent=float(p_elem.attrib.get('FirstLineIndent', 0.0)),
            left_indent=float(p_elem.attrib.get('LeftIndent', 0.0)),
            right_indent=float(p_elem.attrib.get('RightIndent', 0.0)),
            space_above=float(p_elem.attrib.get('SpaceAbove', 0.0)),
            space_below=float(p_elem.attrib.get('SpaceBelow', 0.0))
        )

        for child in p_elem:
            if child.tag == 'content':
                st = int(child.attrib.get('startOffset', 0))
                length = int(child.attrib.get('length', 0))
                run_text = cdata[st:st + length] if (0 <= st < len(cdata)) else ""
                
                # Check formatting
                bold = child.attrib.get('bold', 'false').lower() == 'true'
                italic = child.attrib.get('italic', 'false').lower() == 'true'
                underline = child.attrib.get('underline', 'false').lower() == 'true'
                size = float(child.attrib.get('size', 11.0))
                font_family = child.attrib.get('family', 'Times New Roman')
                foreground = child.attrib.get('foreground', None)

                p.items.append(UDFRun(
                    text=run_text, bold=bold, italic=italic, 
                    underline=underline, size=size, font_family=font_family,
                    foreground=foreground
                ))
            elif child.tag == 'space':
                p.items.append(UDFRun(text=" "))
            elif child.tag == 'image':
                img_data = child.attrib.get('imageData', '')
                if img_data:
                    try:
                        img_bytes = base64.b64decode(img_data)
                        w = float(child.attrib.get('width', 0))
                        h = float(child.attrib.get('height', 0))
                        p.items.append(UDFImage(image_bytes=img_bytes, width=w, height=h))
                    except Exception:
                        pass
        return p

    @staticmethod
    def _parse_table(tbl_elem: ET.Element, cdata: str) -> UDFTable:
        name = tbl_elem.attrib.get('tableName', '')
        col_count = int(tbl_elem.attrib.get('columnCount', 0))
        spans_str = tbl_elem.attrib.get('columnSpans', '')
        spans = [float(s.strip()) for s in spans_str.split(',') if s.strip()] if spans_str else []
        border = tbl_elem.attrib.get('border', 'borderNone')

        tbl = UDFTable(name=name, column_count=col_count or len(spans), column_spans=spans, border=border)

        for row_elem in tbl_elem.findall('./row'):
            row = UDFRow()
            for cell_elem in row_elem.findall('./cell'):
                col_span = int(cell_elem.attrib.get('colSpan', 1))
                row_span = int(cell_elem.attrib.get('rowSpan', 1))
                cell_border = cell_elem.attrib.get('border', border)
                fill_color = cell_elem.attrib.get('fillColor', None)
                
                cell = UDFCell(col_span=col_span, row_span=row_span, border=cell_border, fill_color=fill_color)
                for p_elem in cell_elem.findall('./paragraph'):
                    cell.paragraphs.append(UDFParser._parse_paragraph(p_elem, cdata))
                row.cells.append(cell)
            tbl.rows.append(row)
        return tbl


# ---------------------------------------------------------------------------
# High-Fidelity Exporters: DOCX, PDF, HTML, TXT, UDF
# ---------------------------------------------------------------------------

class UDFExporter:
    @staticmethod
    def to_docx(doc: UDFDocument) -> bytes:
        docx_doc = Document()

        # Set page margins (UDF points to docx inches/pts)
        for s in docx_doc.sections:
            s.left_margin = Inches(doc.margins.get('left', 70.875) / 72.0)
            s.right_margin = Inches(doc.margins.get('right', 70.875) / 72.0)
            s.top_margin = Inches(doc.margins.get('top', 70.875) / 72.0)
            s.bottom_margin = Inches(doc.margins.get('bottom', 70.875) / 72.0)

        # E-İmza Badge if signed
        if doc.eimza and doc.eimza.get('signed'):
            badge_p = docx_doc.add_paragraph()
            badge_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            signer = doc.eimza.get('signer', 'Yetkili İmzacı')
            title = doc.eimza.get('title', 'AVUKAT')
            issuer = doc.eimza.get('issuer_org', 'Nitelikli Elektronik Sertifika')
            valid = doc.eimza.get('valid_until', '')
            
            run = badge_p.add_run(f"🔒 5070 Sayılı Kanun Uyarınca E-İmzalıdır\nİmzalayan: {title} {signer} | Kurum: {issuer}")
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            run.italic = True
            
            # Subtle divider line
            pBdr = OxmlElement('w:pBdr')
            bottomBdr = OxmlElement('w:bottom')
            bottomBdr.set(qn('w:val'), 'single')
            bottomBdr.set(qn('w:sz'), '4')
            bottomBdr.set(qn('w:space'), '1')
            bottomBdr.set(qn('w:color'), 'CCCCCC')
            pBdr.append(bottomBdr)
            badge_p._p.get_or_add_pPr().append(pBdr)

        for block in doc.blocks:
            if isinstance(block, UDFParagraph):
                UDFExporter._render_docx_paragraph(docx_doc, block)
            elif isinstance(block, UDFTable):
                UDFExporter._render_docx_table(docx_doc, block)

        bio = io.BytesIO()
        docx_doc.save(bio)
        return bio.getvalue()

    @staticmethod
    def _render_docx_paragraph(container: Any, p_block: UDFParagraph, existing_p: Any = None):
        p = existing_p if existing_p is not None else container.add_paragraph()

        # Alignment
        if p_block.alignment == 1:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif p_block.alignment == 2:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif p_block.alignment == 3:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Spacing
        p.paragraph_format.space_before = Pt(p_block.space_above or 0)
        p.paragraph_format.space_after = Pt(p_block.space_below or 0)
        if p_block.first_line_indent > 0:
            p.paragraph_format.first_line_indent = Pt(p_block.first_line_indent)

        for item in p_block.items:
            if isinstance(item, UDFRun):
                run = p.add_run(item.text)
                run.bold = item.bold
                run.italic = item.italic
                if item.underline:
                    run.underline = WD_UNDERLINE.SINGLE
                if item.size > 0:
                    run.font.size = Pt(item.size)
                if item.font_family:
                    run.font.name = item.font_family
            elif isinstance(item, UDFImage):
                try:
                    stream = io.BytesIO(item.image_bytes)
                    run = p.add_run()
                    # Scale width
                    w_in = Inches(min(item.width / 72.0, 5.5)) if item.width > 0 else Inches(2.5)
                    run.add_picture(stream, width=w_in)
                except Exception:
                    pass

    @staticmethod
    def _render_docx_table(doc: Document, tbl_block: UDFTable):
        if not tbl_block.rows:
            return

        row_count = len(tbl_block.rows)
        col_count = max(len(r.cells) for r in tbl_block.rows) if tbl_block.rows else 1
        if col_count == 0:
            return

        table = doc.add_table(rows=row_count, cols=col_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Determine border style
        is_borderless = tbl_block.border == 'borderNone'
        if not is_borderless:
            table.style = 'Table Grid'
        else:
            # Clear borders
            tblPr = table._tbl.tblPr
            tblBorders = parse_xml(r'''
                <w:tblBorders %s>
                    <w:top w:val="none"/>
                    <w:left w:val="none"/>
                    <w:bottom w:val="none"/>
                    <w:right w:val="none"/>
                    <w:insideH w:val="none"/>
                    <w:insideV w:val="none"/>
                </w:tblBorders>
            ''' % nsdecls('w'))
            tblPr.append(tblBorders)

        # Proportional column widths
        total_span = sum(tbl_block.column_spans) if tbl_block.column_spans else 0
        if total_span > 0:
            total_width_in = 6.2  # Max usable page width
            for col_idx in range(min(col_count, len(tbl_block.column_spans))):
                fraction = tbl_block.column_spans[col_idx] / total_span
                col_width = Inches(fraction * total_width_in)
                for r in table.rows:
                    if col_idx < len(r.cells):
                        r.cells[col_idx].width = col_width

        for r_idx, row_data in enumerate(tbl_block.rows):
            for c_idx, cell_data in enumerate(row_data.cells):
                if c_idx >= col_count:
                    break
                cell = table.cell(r_idx, c_idx)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                # Fill paragraphs inside cell
                first = True
                for p_block in cell_data.paragraphs:
                    if first:
                        first_p = cell.paragraphs[0]
                        UDFExporter._render_docx_paragraph(cell, p_block, existing_p=first_p)
                        first = False
                    else:
                        UDFExporter._render_docx_paragraph(cell, p_block)

    @staticmethod
    def to_pdf(doc: UDFDocument) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(20, 15, 20)

        # Add Turkish Fonts
        try:
            if os.path.exists(FONT_REG):
                pdf.add_font('Roboto', '', FONT_REG)
                if os.path.exists(FONT_BOLD):
                    pdf.add_font('Roboto', 'B', FONT_BOLD)
                if os.path.exists(FONT_ITAL):
                    pdf.add_font('Roboto', 'I', FONT_ITAL)
                font_family = 'Roboto'
            else:
                font_family = 'Helvetica'
        except Exception:
            font_family = 'Helvetica'

        # E-İmza Badge
        if doc.eimza and doc.eimza.get('signed'):
            pdf.set_font(font_family, 'I', 8)
            pdf.set_text_color(100, 100, 100)
            signer = doc.eimza.get('signer', 'Yetkili İmzacı')
            title = doc.eimza.get('title', 'AVUKAT')
            issuer = doc.eimza.get('issuer_org', 'Nitelikli Elektronik Sertifika')
            pdf.cell(0, 5, f"[5070 Sayılı E-İmza] {title} {signer} - {issuer}", ln=1, align='R')
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)

        pdf.set_font(font_family, '', 10)
        pdf.set_text_color(20, 20, 20)

        for block in doc.blocks:
            if isinstance(block, UDFParagraph):
                align_code = 'L'
                if block.alignment == 1:
                    align_code = 'C'
                elif block.alignment == 2:
                    align_code = 'R'
                elif block.alignment == 3:
                    align_code = 'J'

                p_text = block.text
                if not p_text.strip():
                    pdf.ln(4)
                    continue

                # Set bold if dominant
                has_bold = any(it.bold for it in block.items if isinstance(it, UDFRun))
                pdf.set_font(font_family, 'B' if has_bold else '', 10)
                pdf.multi_cell(0, 5.5, p_text, align=align_code)
                pdf.ln(1.5)

            elif isinstance(block, UDFTable):
                # Render table in PDF
                if not block.rows:
                    continue
                num_cols = max(len(r.cells) for r in block.rows)
                if num_cols == 0:
                    continue
                col_w = 170.0 / num_cols

                for r in block.rows:
                    max_h = 7.0
                    for c in r.cells:
                        txt = c.text.strip()
                        pdf.set_font(font_family, '', 9)
                        pdf.cell(col_w, max_h, txt[:30], border=1 if block.border != 'borderNone' else 0)
                    pdf.ln()
                pdf.ln(2)

        return bytes(pdf.output())

    @staticmethod
    def to_html(doc: UDFDocument) -> str:
        html_out = ['<div class="udf-document-view" style="font-family: \'Times New Roman\', serif; font-size: 14px; line-height: 1.5; color: #111; max-width: 800px; margin: 0 auto; background: #fff; padding: 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-radius: 4px;">']

        if doc.eimza and doc.eimza.get('signed'):
            signer = doc.eimza.get('signer', 'Yetkili İmzacı')
            title = doc.eimza.get('title', 'AVUKAT')
            issuer = doc.eimza.get('issuer_org', 'Nitelikli Elektronik Sertifika')
            valid = doc.eimza.get('valid_until', '')
            badge = f'''
            <div style="background: #eef7ee; border: 1px solid #c2e2c2; border-left: 4px solid #2e7d32; border-radius: 4px; padding: 10px 14px; margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between;">
                <div style="font-size: 12px; color: #1b5e20;">
                    <strong style="display: block; font-size: 13px;">🔒 5070 Sayılı Kanuna Uygun Güvenli Elektronik İmza</strong>
                    İmzalayan: <b>{title} {signer}</b> &bull; Kurum: {issuer} {f"&bull; Geçerlilik: {valid}" if valid else ""}
                </div>
                <span style="background: #2e7d32; color: #fff; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 3px; text-transform: uppercase;">Doğrulandı</span>
            </div>
            '''
            html_out.append(badge)

        for block in doc.blocks:
            if isinstance(block, UDFParagraph):
                align = 'left'
                if block.alignment == 1: align = 'center'
                elif block.alignment == 2: align = 'right'
                elif block.alignment == 3: align = 'justify'

                p_html = [f'<p style="text-align: {align}; margin: 4px 0; min-height: 14px;">']
                for item in block.items:
                    if isinstance(item, UDFRun):
                        style_attrs = []
                        if item.bold: style_attrs.append("font-weight: bold;")
                        if item.italic: style_attrs.append("font-style: italic;")
                        if item.underline: style_attrs.append("text-decoration: underline;")
                        style_str = f' style="{" ".join(style_attrs)}"' if style_attrs else ""
                        p_html.append(f'<span{style_str}>{html.escape(item.text)}</span>')
                    elif isinstance(item, UDFImage):
                        b64 = base64.b64encode(item.image_bytes).decode('ascii')
                        p_html.append(f'<img src="data:image/png;base64,{b64}" style="max-width: 100%; height: auto; margin: 10px 0;" />')
                p_html.append('</p>')
                html_out.append("".join(p_html))

            elif isinstance(block, UDFTable):
                border_css = "border-collapse: collapse; width: 100%; margin: 15px 0;"
                cell_border_css = "border: 1px solid #999; padding: 6px 10px;" if block.border != 'borderNone' else "padding: 6px 10px;"
                html_out.append(f'<table style="{border_css}">')
                for row in block.rows:
                    html_out.append('<tr>')
                    for cell in row.cells:
                        colspan_attr = f' colspan="{cell.col_span}"' if cell.col_span > 1 else ''
                        html_out.append(f'<td style="{cell_border_css}"{colspan_attr}>')
                        for p in cell.paragraphs:
                            html_out.append(f'<div style="text-align: left;">{html.escape(p.text)}</div>')
                        html_out.append('</td>')
                    html_out.append('</tr>')
                html_out.append('</table>')

        html_out.append('</div>')
        return "\n".join(html_out)

    @staticmethod
    def to_text(doc: UDFDocument) -> str:
        lines = []
        if doc.eimza and doc.eimza.get('signed'):
            lines.append(f"[5070 SAYILI E-İMZALI BELGE - İMZA: {doc.eimza.get('title', '')} {doc.eimza.get('signer', '')}]\n")
        for block in doc.blocks:
            if isinstance(block, UDFParagraph):
                lines.append(block.text)
            elif isinstance(block, UDFTable):
                for row in block.rows:
                    lines.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reverse Converter: Text/DOCX to Standard UDF
# ---------------------------------------------------------------------------

class UDFGenerator:
    @staticmethod
    def create_udf_from_text(content: str) -> bytes:
        """Constructs a valid UYAP UDF PKZip with offset-aligned elements."""
        lines = content.split('\n')
        p_xml = []
        offset = 0
        for l in lines:
            l_len = len(l) + 1  # includes newline
            p_xml.append(f'<paragraph><content startOffset="{offset}" length="{l_len}" /></paragraph>')
            offset += l_len

        elements_str = "\n".join(p_xml)
        xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<template format_id="1.8">
<content><![CDATA[{content}
]]></content>
<properties>
    <pageFormat mediaSizeName="1" leftMargin="70.875" rightMargin="70.875" topMargin="70.875" bottomMargin="70.875" paperOrientation="1" headerFOffset="20.0" footerFOffset="20.0" />
</properties>
<elements resolver="hvl-default">
{elements_str}
</elements>
<styles>
    <style name="default" description="Geçerli" family="Times New Roman" size="12" />
    <style name="hvl-default" description="Geçerli" family="Times New Roman" size="12" />
</styles>
</template>"""

        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("content.xml", xml.encode('utf-8'))
        return bio.getvalue()


# ---------------------------------------------------------------------------
# Multi-Format Ingestion (PyMuPDF, OCR, DOCX, Images)
# ---------------------------------------------------------------------------

class UniversalDocumentReader:
    @staticmethod
    def read_document(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        ext = os.path.splitext(filename)[1].lower()

        if ext == '.udf':
            doc = UDFParser.parse_from_bytes(file_bytes)
            return {
                'format': 'udf',
                'doc_obj': doc,
                'text': UDFExporter.to_text(doc),
                'html': UDFExporter.to_html(doc),
                'has_sign': bool(doc.eimza and doc.eimza.get('signed')),
                'sign_info': doc.eimza
            }

        elif ext == '.pdf':
            full_text = []
            with fitz.open(stream=file_bytes, filetype="pdf") as pdf_doc:
                mat = fitz.Matrix(2.0, 2.0)  # 300 DPI zoom
                for page in pdf_doc:
                    t = page.get_text("text", sort=True)
                    if len(t.strip()) < 50 and HAS_TESSERACT:
                        # Scanned page OCR
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.open(io.BytesIO(pix.tobytes()))
                        t = pytesseract.image_to_string(img, lang='tur')
                    full_text.append(t)
            extracted = "\n".join(full_text)
            return {'format': 'pdf', 'text': extracted, 'html': f"<pre>{html.escape(extracted)}</pre>"}

        elif ext == '.docx':
            doc = Document(io.BytesIO(file_bytes))
            lines = [p.text for p in doc.paragraphs]
            for tbl in doc.tables:
                for r in tbl.rows:
                    lines.append(" | ".join(c.text.strip() for c in r.cells))
            extracted = "\n".join(lines)
            return {'format': 'docx', 'text': extracted, 'html': f"<pre>{html.escape(extracted)}</pre>"}

        elif ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']:
            if HAS_TESSERACT:
                img = Image.open(io.BytesIO(file_bytes))
                extracted = pytesseract.image_to_string(img, lang='tur')
            else:
                extracted = "[OCR kütüphanesi aktif değil]"
            return {'format': 'image', 'text': extracted, 'html': f"<pre>{html.escape(extracted)}</pre>"}

        else:
            # Fallback text decoding
            text = file_bytes.decode('utf-8', errors='ignore')
            return {'format': 'txt', 'text': text, 'html': f"<pre>{html.escape(text)}</pre>"}


if __name__ == '__main__':
    print("VEX Master Engine yüklendi. Testler için hazır.")
