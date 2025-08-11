import streamlit as st
import streamlit.components.v1 as components
import configparser, os, re
from datetime import datetime, date
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import json, html



# -------- Helpers --------
def load_config():
    cfg_path = "config.ini"
    if not os.path.exists(cfg_path):
        cp = configparser.ConfigParser()
        cp["formats"] = {
            "file_formats": "MOV, MXF, MP4, AVI, ProRes, DNxHD",
            "video_formats": "SD, HD, 4K",
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            cp.write(f)

    cp = configparser.ConfigParser()
    cp.read(cfg_path, encoding="utf-8")
    file_formats = [s.strip() for s in cp.get("formats", "file_formats").split(",") if s.strip()]
    video_formats = [s.strip() for s in cp.get("formats", "video_formats").split(",") if s.strip()]
    return file_formats, video_formats

LANGUAGES = [
    ("FR","Français"), ("ES","Espagnol"), ("EN","Anglais"), ("HI","Hindi"),
    ("AR","Arabe"), ("BN","Bengali"), ("PT","Portugais"), ("RU","Russe"),
    ("JA","Japonais"), ("PA","Pendjabi"), ("MR","Marathi"), ("TE","Télougou"),
    ("VI","Vietnamien"), ("KO","Coréen"), ("ZH","Mandarin"), ("DE","Allemand"),
    ("TA","Tamoul"), ("UR","Ourdou"), ("JV","Javanais"), ("IT","Italien")
]
SUBTITLES = LANGUAGES + [("NOSUB", "NoSub")]
CADENCES = ["", "23.976", "24", "25", "29.97", "30", "50", "59.94"]
AUDIO_FORMATS = [("20","Stereo"), ("51","Surround")]

def sanitize(text: str) -> str:
    if not text: return ""
    tmp = re.sub(r"[^A-Za-z0-9\s]+", "", text)
    return re.sub(r"_+", "_", tmp.strip().replace(" ", "_"))

def build_filename(program, version, dt, language, subtitles, fileformat, videoformat,
                   videoaspect_raw, videores, cadence, audioformat, audiocodec):
    program = sanitize(program)
    version = sanitize(version)
    audiocodec = sanitize(audiocodec)
    videores = sanitize(videores)
    date_code = dt.strftime("%y%m%d") if isinstance(dt, date) else datetime.now().strftime("%y%m%d")
    videoaspect = re.sub(r"[.,]", "", videoaspect_raw or "")
    if subtitles == "NOSUB":
        sub_seg = "NOSUB"
    elif subtitles:
        sub_seg = f"ST{subtitles}"
    else:
        sub_seg = ""
    segments = [program]
    if version: segments.append(version)
    lang_seg = f"{language}-{sub_seg}" if sub_seg else language
    segments.append(lang_seg)
    segments += [fileformat, videoformat, videoaspect, videores, cadence, audioformat, audiocodec, date_code]
    return "_".join(seg for seg in segments if seg)

def ensure_state():
    for k, v in (("entries", []), ("id_counter", 0), ("program_name", "")):
        if k not in st.session_state: st.session_state[k] = v

def next_id():
    st.session_state.id_counter += 1
    return f"{st.session_state.id_counter:02d}"

def pdf_bytes(entries, program):
    today = datetime.now().strftime("%Y%m%d")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # Titre
    y = h - 80
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, f"EXPORT LIST {sanitize(program)} {today}")
    y -= 40

    # Cartes
    card_h = 70
    pad = 12
    for e in entries:
        if y - card_h < 50:
            c.showPage()
            y = h - 80

        x = 40
        card_w = w - 2 * x

        # flat card
        c.setFillColorRGB(0.9, 0.95, 1.0)
        c.roundRect(x, y - card_h, card_w, card_h, 8, fill=True, stroke=False)
        c.setStrokeColorRGB(0.6, 0.6, 0.8)
        c.roundRect(x, y - card_h, card_w, card_h, 8, fill=False, stroke=True)

        # icône fichier
        icon_x, icon_y = x + pad, y - pad - 20
        c.setFillColorRGB(0.7, 0.7, 0.7)
        c.rect(icon_x, icon_y, 14, 18, fill=True, stroke=False)
        p = c.beginPath()
        p.moveTo(icon_x + 9, icon_y + 18)
        p.lineTo(icon_x + 14, icon_y + 18)
        p.lineTo(icon_x + 14, icon_y + 13)
        p.close()
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)

        tx = icon_x + 14 + pad
        c.setFont("Helvetica-Bold", 12)
        c.drawString(tx, y - pad - 4, (e.get("filename",""))[:50])
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(tx, y - pad - 20, (e.get("description",""))[:60])
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.4, 0.4, 0.6)
        c.drawString(tx, y - pad - 34, f"ID: {e.get('id','')}")
        c.setFillColorRGB(0,0,0)
        y -= (card_h + pad)

    c.save()
    buf.seek(0)
    return buf.getvalue(), f"{sanitize(program)}_{today}_export_list.pdf"

def bitrate_h264_high(mbps: float, total_sec: int):
    size_mb = (mbps * total_sec) / 8
    size_gb = size_mb / 1024
    return size_mb*1.01, size_gb*1.01  # +1% overhead conteneur

# -------- UI --------
st.set_page_config(page_title="Export Namer + Bitrate", layout="wide")
ensure_state()
file_formats, video_formats = load_config()

st.title("Clean Masters Filename Generator")

with st.form("form"):
    col1, col2, col3 = st.columns([1,1,1])
    program = col1.text_input("PROGRAM NAME *", value=st.session_state.program_name, key="program_name_input")
    version = col2.text_input("VERSION", key="version")
    form_date = col3.date_input("DATE *", value=date.today(), format="YYYY-MM-DD", key="form_date")

    col4, col5, col6 = st.columns([1,1,1])
    language = col4.selectbox("LANGUAGE *", options=[c for c,_ in LANGUAGES], format_func=lambda x: dict(LANGUAGES)[x])
    subtitles = col5.selectbox("SUBTITLES *", options=[c for c,_ in SUBTITLES], format_func=lambda x: dict(SUBTITLES).get(x, x))
    fileformat = col6.selectbox("FILE FORMAT *", options=file_formats)

    col7, col8, col9 = st.columns([1,1,1])
    videoformat = col7.selectbox("VIDEO FORMAT *", options=video_formats)
    videoaspect = col8.text_input("VIDEO ASPECT (ex: 1.85 ou 1,85)", value="")
    videores = col9.text_input("VIDEO RESOLUTION (ex: 1920x1080)", value="")

    col10, col11, col12 = st.columns([1,1,1])
    cadence = col10.selectbox("CADENCE", options=CADENCES, index=0)
    audioformat = col11.selectbox("AUDIO FORMAT *", options=[c for c,_ in AUDIO_FORMATS], format_func=lambda x: dict(AUDIO_FORMATS)[x] + f" ({x})")
    audiocodec = col12.text_input("AUDIO CODEC", value="")

    description = st.text_input("Description", value="")

submitted = st.form_submit_button("Add Filename entry")
if submitted:
    required_ok = all([program, form_date, language, subtitles, fileformat, videoformat, audioformat])
    if not required_ok:
        st.error("Please fill all required fields (*)")
    else:
        fname = build_filename(
            program, version, form_date, language, subtitles, fileformat, videoformat,
            videoaspect, videores, cadence, audioformat, audiocodec
        )
        # --- Segments typés pour couleurs stables ---
        prog = sanitize(program)
        vers = sanitize(version)
        date_code = form_date.strftime("%y%m%d")
        videoaspect_clean = re.sub(r"[.,]", "", videoaspect or "")
        videores_clean = sanitize(videores)
        audiocodec_clean = sanitize(audiocodec)
        if subtitles == "NOSUB":
            sub_seg = "NOSUB"
        elif subtitles:
            sub_seg = f"ST{subtitles}"
        else:
            sub_seg = ""
        lang_seg = f"{language}-{sub_seg}" if sub_seg else language

        typed = [("PROGRAM", prog)]
        if vers: typed.append(("VERSION", vers))
        typed += [
            ("LANG_SUB", lang_seg),
            ("FILE_FORMAT", fileformat),
            ("VIDEO_FORMAT", videoformat),
        ]
        if videoaspect_clean: typed.append(("VIDEO_ASPECT", videoaspect_clean))
        if videores_clean:    typed.append(("RESOLUTION", videores_clean))
        if cadence:           typed.append(("CADENCE", cadence))
        typed.append(("AUDIO_FORMAT", audioformat))
        if audiocodec_clean:  typed.append(("AUDIO_CODEC", audiocodec_clean))
        typed.append(("DATE", date_code))

        st.session_state.program_name = program
        st.session_state.entries.append({
            "id": next_id(),
            "filename": fname,
            "description": description or "",
            "segments": typed,  # <— pour rendu coloré stable
        })
        st.success("Entry added.")


st.subheader("KISS File size Calculator")
bc1, bc2, bc3, bc4, bc5 = st.columns([1,1,1,1,2])
dur_h = bc1.number_input("Heures", min_value=0, step=1, value=0)
dur_m = bc2.number_input("Minutes", min_value=0, max_value=59, step=1, value=0)
dur_s = bc3.number_input("Secondes", min_value=0, max_value=59, step=1, value=0)
bitrate_mbps = bc4.number_input("Débit (Mbps)", min_value=0.0, step=0.1, value=25.0)
if bc5.button("Calculer"):
    total_sec = int(dur_h)*3600 + int(dur_m)*60 + int(dur_s)
    mb, gb = bitrate_h264_high(bitrate_mbps, total_sec)
    st.info(f"Taille estimée : ~{mb:.2f} MB ({gb:.2f} GB)")

st.subheader("Entries")
if not st.session_state.entries:
    st.caption("Aucune entrée pour l’instant.")
else:
    # Couleurs pour chaque segment (texte uniquement)
    PALETTE = ["#1565C0", "#2E7D32", "#AD1457", "#EF6C00", "#6A1B9A",
               "#00838F", "#C62828", "#283593", "#6D4C41", "#2E7D32"]

    to_delete = []
    for i, e in enumerate(st.session_state.entries):
        # Ligne unique : [Nom coloré + Copier] | [Description] | [Supprimer]
        col_name, col_desc, col_del = st.columns([6, 4, 1])

        # --- Col 1 : Nom coloré + bouton Copier (vraiment côte à côte) ---
        with col_name:
            segs = e["filename"].split("_")
            colored = []
            for idx, seg in enumerate(segs):
                color = PALETTE[idx % len(PALETTE)]
                colored.append(
                    f"<span style='color:{color};font-weight:600'>{html.escape(seg)}</span>"
                )
            colored_html = "_".join(colored)

            btn_id = f"copybtn_{e['id']}"
            copy_text = json.dumps(e["filename"])  # sûr pour JS

            components.html(
                f"""
                <div style="display:flex;align-items:center;gap:10px;">
                  <div style="font-family:monospace;font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;">
                    {colored_html}
                  </div>
                  <button id="{btn_id}"
                          style="padding:6px 12px;border:1px solid #999;border-radius:8px;background:#f8f9fa;cursor:pointer;white-space:nowrap;">
                    Copier
                  </button>
                </div>
                <script>
                  (function(){{
                    const btn = document.getElementById("{btn_id}");
                    if (btn) {{
                      btn.addEventListener('click', function() {{
                        navigator.clipboard.writeText({copy_text});
                      }});
                    }}
                  }})();
                </script>
                """,
                height=40,
            )

        # --- Col 2 : Description (pas d’étiquette, placeholder, max 50) ---
        with col_desc:
            new_desc = st.text_input(
                label="",
                value=e["description"],
                key=f"desc_{e['id']}",
                max_chars=50,
                placeholder="Description (max 50 caractères)",
                label_visibility="collapsed",
            )
            st.session_state.entries[i]["description"] = new_desc

        # --- Col 3 : Supprimer ---
        with col_del:
            if st.button("Supprimer", key=f"del_{e['id']}"):
                to_delete.append(i)

    if to_delete:
        for idx in reversed(to_delete):
            st.session_state.entries.pop(idx)
        st.rerun()



# Export PDF
st.divider()
if st.session_state.entries:
    data, fname = pdf_bytes(st.session_state.entries, st.session_state.get("program_name", "PROGRAM"))
    st.download_button("Export PDF Report", data=data, file_name=fname, mime="application/pdf")
