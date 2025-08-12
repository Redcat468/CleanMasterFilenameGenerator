import streamlit as st
import streamlit.components.v1 as components
import configparser, os, re
from datetime import datetime, date
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import json, html
import base64
from pathlib import Path


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
AUDIO_FORMATS = [(""),("20","Stereo"), ("51","Surround"), ("71","7.1 Surround")]


def renumber_entries():
    """Force les IDs à 01, 02, 03… selon l’ordre actuel de st.session_state.entries."""
    for idx, entry in enumerate(st.session_state.entries):
        entry["id"] = f"{idx+1:02d}"

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

    # Titre (avec logo si dispo)
    y = h - 80
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, y - 20, width=50, height=50, mask='auto', preserveAspectRatio=True)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, y, f"EXPORT LIST {sanitize(program)} {today}")
    y -= 40

    pad = 12
    vpad_bottom = 10
    corner = 10
    shadow_offset = 2
    icon_path = "file-icon.png"
    icon_w, icon_h = 26, 26  # icône un peu plus grosse

    for e in entries:
        # --- Calcule les positions de texte pour connaître la hauteur utile ---
        has_desc = bool((e.get("description") or "").strip())
        # Baselines texte (plus bas = plus petit en Y)
        filename_y = y - pad - 6
        desc_y     = y - pad - 24 if has_desc else filename_y

        # Bloc icône + ID
        icon_x = 40 + pad
        icon_y = y - pad - icon_h            # top-align de l’icône
        has_id = bool((e.get("id") or "").strip())
        id_y   = icon_y - 10 if has_id else icon_y  # ID situé sous l’icône

        # Le point le plus bas du contenu (le plus petit Y)
        content_bottom_y = min(desc_y, id_y)

        # Hauteur de carte dynamique (avec marge basse)
        card_h = (y - (content_bottom_y - vpad_bottom))
        # Garde-fous sur la hauteur
        if card_h < 48:
            card_h = 48

        # Saut de page si besoin
        if y - card_h < 60:
            c.showPage()
            y = h - 80
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, y, f"EXPORT LIST {sanitize(program)} {today}")
            y -= 40
            # Recalcule baselines avec le nouveau y
            filename_y = y - pad - 6
            desc_y     = y - pad - 24 if has_desc else filename_y
            icon_y     = y - pad - icon_h
            id_y       = icon_y - 10 if has_id else icon_y
            content_bottom_y = min(desc_y, id_y)
            card_h = (y - (content_bottom_y - vpad_bottom))
            if card_h < 48:
                card_h = 48

        x = 40
        card_w = w - 2 * x

        # --- Ombre légère (offset) ---
        c.setFillColorRGB(0.85, 0.87, 0.92)
        c.roundRect(x + shadow_offset, y - card_h - shadow_offset, card_w, card_h, corner, fill=True, stroke=False)

        # --- Carte blanche moderne + bordure subtile ---
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(x, y - card_h, card_w, card_h, corner, fill=True, stroke=False)
        c.setStrokeColorRGB(0.88, 0.88, 0.92)
        c.roundRect(x, y - card_h, card_w, card_h, corner, fill=False, stroke=True)

        # --- Icône fichier (image png) ---
        if os.path.exists(icon_path):
            c.drawImage(icon_path, icon_x, icon_y, width=icon_w, height=icon_h, mask='auto', preserveAspectRatio=True)
        else:
            # Fallback simple si l’icône manque
            c.setFillColorRGB(1.0, 0.84, 0.0)
            c.rect(icon_x, icon_y, icon_w, icon_h, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)

        # --- ID sous l’icône, centré (sans libellé) ---
        if has_id:
            id_text = str(e.get('id', '')).strip()
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.35, 0.40, 0.55)
            tw = c.stringWidth(id_text, "Helvetica", 9)
            cx = icon_x + icon_w / 2.0
            c.drawString(cx - tw / 2.0, icon_y - 10, id_text)
            c.setFillColorRGB(0, 0, 0)

        # --- Texte à droite de l’icône ---
        tx = icon_x + icon_w + pad
        c.setFont("Helvetica-Bold", 12)
        c.drawString(tx, filename_y, (e.get("filename", ""))[:80])

        c.setFont("Helvetica-Oblique", 10)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        if has_desc:
            c.drawString(tx, desc_y, (e.get("description", ""))[:90])
        c.setFillColorRGB(0, 0, 0)

        # Avance pour la carte suivante
        y -= (card_h + pad)

    c.save()
    buf.seek(0)
    return buf.getvalue(), f"{sanitize(program)}_{today}_export_list.pdf"



def bitrate_h264_high(mbps: float, total_sec: int):
    size_mb = (mbps * total_sec) / 8
    size_gb = size_mb / 1024
    return size_mb*1.01, size_gb*1.01  # +1% overhead conteneur



def build_typed_segments(program, version, form_date, language, subtitles,
                         fileformat, videoformat, videoaspect, videores,
                         cadence, audioformat, audiocodec):
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
    if vers:
        typed.append(("VERSION", vers))
    typed += [
        ("LANG_SUB",     lang_seg),
        ("FILE_FORMAT",  fileformat),
        ("VIDEO_FORMAT", videoformat),
    ]
    if videoaspect_clean:
        typed.append(("VIDEO_ASPECT", videoaspect_clean))
    if videores_clean:
        typed.append(("RESOLUTION",   videores_clean))
    if cadence:
        typed.append(("CADENCE",      cadence))
    typed.append(("AUDIO_FORMAT", audioformat))
    if audiocodec_clean:
        typed.append(("AUDIO_CODEC",  audiocodec_clean))
    typed.append(("DATE", date_code))
    return typed





# -------- UI --------
st.set_page_config(page_title="Clean Masters Filename Generator", layout="wide")
ensure_state()
file_formats, video_formats = load_config()

# Affichage logo + titre (logo centré verticalement, hauteur max)
logo_path = Path("logo.png")
if logo_path.exists():
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
    st.markdown(
        f"""
        <style>
          .app-header {{
            display:flex; align-items:center; gap:16px;
            margin-bottom: 8px;
          }}
          .app-header img {{
            max-height: 64px;   /* limite la hauteur du logo */
            height: auto; width: auto;
          }}
          .app-header h1 {{
            margin: 0; line-height: 1.1;
          }}
          @media (max-width: 640px) {{
            .app-header img {{ max-height: 48px; }}
          }}
        </style>
        <div class="app-header">
          <img src="data:image/png;base64,{logo_b64}" alt="Logo">
          <h1>Clean Masters Filename Generator</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
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
            typed = build_typed_segments(
                program, version, form_date, language, subtitles, fileformat, videoformat,
                videoaspect, videores, cadence, audioformat, audiocodec
            )
            st.session_state.program_name = program
            st.session_state["id_counter"] = st.session_state.get("id_counter", 0) + 1
            st.session_state.entries.append({
                "id": "",  # placeholder, on renumérote juste après
                "filename": fname,
                "description": description or "",
                "segments": typed,
            })
            renumber_entries()
            st.success("Entry added.")



st.subheader("Entries")
if not st.session_state.entries:
    st.caption("Aucune entrée pour l’instant.")
else:
    TYPE_COLORS = {
        "PROGRAM":      "#1565C0",
        "VERSION":      "#6A1B9A",
        "LANG_SUB":     "#2E7D32",
        "FILE_FORMAT":  "#EF6C00",
        "VIDEO_FORMAT": "#00838F",
        "VIDEO_ASPECT": "#AD1457",
        "RESOLUTION":   "#283593",
        "CADENCE":      "#6D4C41",
        "AUDIO_FORMAT": "#C62828",
        "AUDIO_CODEC":  "#455A64",
        "DATE":         "#4FC3F7",  # bleu clair fixe
    }
    renumber_entries()
    to_delete = []
    for i, e in enumerate(st.session_state.entries):
        col_name, col_desc, col_del = st.columns([6, 4, 1])

        # --- Nom coloré par TYPE + Copier à côté, avec animation ---
        with col_name:
            seglist = e.get("segments", [])
            if not seglist:
                # si vieilles entrées sans 'segments', on ne colore pas correctement (tout serait bleu) :
                # supprime-les et ré-ajoute-les pour bénéficier des couleurs fixes
                seglist = [("PROGRAM", part) for part in e["filename"].split("_")]

            colored_parts = []
            for t, val in seglist:
                color = TYPE_COLORS.get(t, "#111")
                colored_parts.append(
                    f"<span style='color:{color};font-weight:600'>{html.escape(str(val))}</span>"
                )
            colored_html = "_".join(colored_parts)

            btn_id = f"copybtn_{e['id']}"
            copy_text = json.dumps(e["filename"])

            components.html(
                f"""
                <style>
                  .copy-btn {{
                    padding:6px 12px; border:1px solid #999; border-radius:8px; background:#f8f9fa; cursor:pointer;
                    transition: background 0.25s, transform 0.08s;
                    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                    white-space:nowrap;
                  }}
                  .copy-btn:active {{ transform: scale(0.98); }}
                  .copied-anim {{ animation: pulseCopy 700ms ease; }}
                  @keyframes pulseCopy {{
                    0%   {{ background:#f8f9fa; }}
                    40%  {{ background:#c8f7d0; }}
                    100% {{ background:#f8f9fa; }}
                  }}
                </style>
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:nowrap;min-width:0;">
                  <div style="font-family:monospace;font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    {colored_html}
                  </div>
                  <button id="{btn_id}" class="copy-btn" aria-label="Copier">Copier</button>
                </div>
                <script>
                  (function(){{
                    var btn = document.getElementById("{btn_id}");
                    if(!btn) return;
                    btn.addEventListener("click", function(){{
                      navigator.clipboard.writeText({copy_text}).then(function(){{
                        btn.classList.remove("copied-anim");
                        void btn.offsetWidth;
                        btn.classList.add("copied-anim");
                        var old = btn.textContent;
                        btn.textContent = "Copié ✓";
                        setTimeout(function(){{ btn.textContent = "Copier"; }}, 900);
                      }});
                    }});
                  }})();
                </script>
                """,
                height=46,
            )

        # --- Description à droite (placeholder, max 50, pas d’étiquette) ---
        with col_desc:
            new_desc = st.text_input(
                label="",
                value=e.get("description",""),
                key=f"desc_{e['id']}",
                max_chars=50,
                placeholder="Description (max 50)",
                label_visibility="collapsed",
            )
            st.session_state.entries[i]["description"] = new_desc

        # --- Supprimer (même ligne) ---
        with col_del:
            if st.button("Supprimer", key=f"del_{e['id']}"):
                to_delete.append(i)

    if to_delete:
        for idx in reversed(to_delete):
            st.session_state.entries.pop(idx)
        renumber_entries()
        st.rerun()



# Export PDF
st.divider()
if st.session_state.entries:
    renumber_entries()
    data, fname = pdf_bytes(st.session_state.entries, st.session_state.get("program_name", "PROGRAM"))
    st.download_button("Export PDF Report", data=data, file_name=fname, mime="application/pdf")



with st.expander("Quick file size Calculator"):
    # Harmonise la hauteur des widgets et du bouton
    st.markdown("""
    <style>
      /* Hauteur des champs numériques */
      div[data-testid="stNumberInput"] input { height: 40px; }
      div[data-testid="stNumberInput"] label { margin-bottom: 2px; }
      /* Hauteur du bouton Compute */
      div.stButton > button { height: 40px; padding: 0 14px; }
    </style>
    """, unsafe_allow_html=True)

    # Utilise un form pour un submit propre et un spacer pour l'alignement vertical
    with st.form("filesize_form"):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 0.9])

        with c1:
            dur_h = st.number_input("Heures", min_value=0, step=1, value=0)
        with c2:
            dur_m = st.number_input("Minutes", min_value=0, max_value=59, step=1, value=0)
        with c3:
            dur_s = st.number_input("Secondes", min_value=0, max_value=59, step=1, value=0)
        with c4:
            bitrate_mbps = st.number_input("Débit (Mbps)", min_value=0.0, step=0.1, value=25.0)
        with c5:
            # Spacer pour aligner le bouton sur la ligne des inputs
            st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
            do_compute = st.form_submit_button("Compute")

        if do_compute:
            total_sec = int(dur_h)*3600 + int(dur_m)*60 + int(dur_s)
            mb, gb = bitrate_h264_high(bitrate_mbps, total_sec)
            st.info(f"Taille estimée : ~{mb:.2f} MB ({gb:.2f} GB)")




# --- Footer (fixed bottom) ---
APP_NAME     = "Clean Masters Filename Generator"
APP_VERSION  = "v1.0"
REPO_URL     = "https://github.com/Redcat468/cleanmasterfilenamegenerator"
AUTHOR_NAME  = "Félix Abt – Cairn Studios"
AUTHOR_URL   = "https://github.com/Redcat468"
LICENSE_NAME = "CC BY-NC-SA 4.0"
LICENSE_URL  = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

# --- Footer (non fixe, compatible thème sombre) ---
APP_NAME     = "Clean Masters Filename Generator"
APP_VERSION  = "v1.0"
REPO_URL     = "https://github.com/Redcat468/cleanmasterfilenamegenerator"
AUTHOR_NAME  = "Félix Abt – Cairn Studios"
AUTHOR_URL   = "https://github.com/Redcat468"
LICENSE_NAME = "CC BY-NC-SA 4.0"
LICENSE_URL  = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

st.markdown(
    f"""
    <style>
      /* Footer non fixe : suit le flux normal de la page */
      .app-footer {{
        margin-top: 24px;
        padding: 12px 16px;
        border-top: 1px solid rgba(0,0,0,0.08);
        color: inherit;           /* hérite du thème (texte) */
        background: transparent;  /* pas de aplat : respecte le thème */
      }}

      /* Forcer la bordure adaptée au mode sombre si présent */
      html[data-theme="dark"] .app-footer,
      body[data-theme="dark"] .app-footer {{
        border-top-color: rgba(255,255,255,0.12);
        color: inherit;
        background: transparent;
      }}

      .app-footer p {{ margin: 0; text-align: center; }}
      .app-footer a {{
        color: inherit;
        text-decoration: none;
        border-bottom: 1px dashed currentColor;
      }}
      .app-footer a:hover {{ border-bottom-style: solid; }}

      @media (max-width: 640px) {{
        .app-footer {{ font-size: 12px; }}
      }}
    </style>

    <footer class="app-footer">
      <p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/">
        <a property="dct:title" rel="cc:attributionURL" href="{REPO_URL}" target="_blank" rel="noopener noreferrer">
          {APP_NAME} {APP_VERSION}
        </a>
        by
        <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="{AUTHOR_URL}" target="_blank" rel="noopener noreferrer">
          {AUTHOR_NAME}
        </a>
        is licensed under
        <a href="{LICENSE_URL}" target="_blank" rel="license noopener noreferrer">{LICENSE_NAME}</a>
      </p>
    </footer>
    """,
    unsafe_allow_html=True,
)
