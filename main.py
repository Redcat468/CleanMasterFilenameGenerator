from flask import Flask, render_template, request, jsonify, send_file
import configparser, re
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# --- Helpers ---
def sanitize(text: str) -> str:
    if not text:
        return ''
    tmp = re.sub(r'[^A-Za-z0-9\s]+', '', text)
    return re.sub(r'_+', '_', tmp.strip().replace(' ', '_'))

# --- Routes ---
@app.route('/')
def index():
    config = configparser.ConfigParser()
    config.read('config.ini')
    file_formats  = [f.strip() for f in config.get('formats', 'file_formats').split(',')]
    video_formats = [v.strip() for v in config.get('formats', 'video_formats').split(',')]

    LANGUAGES = [
        ('ZH','Mandarin'), ('ES','Espagnol'), ('EN','Anglais'), ('HI','Hindi'),
        ('AR','Arabe'),    ('BN','Bengali'),  ('PT','Portugais'), ('RU','Russe'),
        ('JA','Japonais'), ('PA','Pendjabi'), ('MR','Marathi'),   ('TE','Télougou'),
        ('VI','Vietnamien'), ('KO','Coréen'), ('FR','Français'),  ('DE','Allemand'),
        ('TA','Tamoul'),   ('UR','Ourdou'),  ('JV','Javanais'),  ('IT','Italien')
    ]
    SUBTITLES = LANGUAGES + [('NOSUB','NoSub')]
    CADENCES = ['', '23.976', '24', '25', '29.97', '30', '50', '59.94']
    AUDIO_FORMATS = [('20','Stereo'), ('51','Surround')]

    return render_template('index.html',
        languages=LANGUAGES,
        subtitles=SUBTITLES,
        file_formats=file_formats,
        video_formats=video_formats,
        cadences=CADENCES,
        audio_formats=AUDIO_FORMATS
    )

@app.route('/add', methods=['POST'])
def add():
    data = request.get_json()
    program     = sanitize(data.get('program_name'))
    version     = sanitize(data.get('version'))
    date_str    = data.get('date', '')
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        dt = datetime.now()
    date_code   = dt.strftime('%y%m%d')

    language    = data.get('language', '')
    subtitles   = data.get('subtitles', '')
    subtitle_seg = 'NOSUB' if subtitles=='NOSUB' else (f"ST{subtitles}" if subtitles else '')

    fileformat  = data.get('file_format', '')
    videoformat = data.get('video_format', '')
    aspect_raw  = data.get('video_aspect','')
    videoaspect = re.sub(r'[.,]', '', aspect_raw)
    videores    = sanitize(data.get('video_resolution',''))
    cadence     = data.get('cadence','')
    audioformat = data.get('audio_format','')
    audiocodec  = sanitize(data.get('audio_codec',''))
    description = data.get('description','')

    segments = [program]
    if version:
        segments.append(version)
    segments.append(f"{language}-{subtitle_seg}" if subtitle_seg else language)
    segments += [
        fileformat, videoformat, videoaspect,
        videores, cadence, audioformat,
        audiocodec, date_code
    ]
    filename = "_".join(seg for seg in segments if seg)
    return jsonify({'filename': filename, 'description': description})

@app.route('/export-pdf', methods=['POST'])
def export_pdf():
    data    = request.get_json()
    program = sanitize(data.get('program_name', ''))
    entries = data.get('entries', [])

    today = datetime.now().strftime('%Y%m%d')

    buffer = BytesIO()
    c      = canvas.Canvas(buffer, pagesize=A4)
    w, h   = A4

    # Titre
    y = h - 80
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, y, f"EXPORT LIST {program} {today}")
    y -= 40

    # Cartes flat design
    card_height = 70
    padding     = 12
    for entry in entries:
        if y - card_height < 50:
            c.showPage()
            y = h - 80

        x      = 40
        card_w = w - 2 * x

        # Fond pastel et contour
        c.setFillColorRGB(0.9, 0.95, 1.0)
        c.roundRect(x, y - card_height, card_w, card_height, 8, fill=True, stroke=False)
        c.setStrokeColorRGB(0.6, 0.6, 0.8)
        c.roundRect(x, y - card_height, card_w, card_height, 8, fill=False, stroke=True)

        # Icône de fichier
        icon_x = x + padding
        icon_y = y - padding - 20
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

        text_x = icon_x + 14 + padding

        # Nom (ligne 1)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(text_x, y - padding - 4, entry.get('filename','')[:50])

        # Description (ligne 2)
        c.setFont('Helvetica-Oblique', 10)
        c.drawString(text_x, y - padding - 20, entry.get('description','')[:60])

        # ID (ligne 3)
        c.setFont('Helvetica', 9)
        c.setFillColorRGB(0.4, 0.4, 0.6)
        c.drawString(text_x, y - padding - 34, f"ID: {entry.get('id','')}")

        y -= (card_height + padding)

    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{program}_{today}_export_list.pdf",
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)
