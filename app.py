"""
Backend системи автоматичного озвучування текстів.
Рушій: Microsoft Edge TTS (безкоштовний, без обмежень)
"""
import os
import io
import base64
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import edge_tts

app = Flask(__name__, static_folder="static", template_folder="static")
CORS(app)

# ============================================================================
# ФРОНТЕНД
# ============================================================================

@app.route('/')
def index():
    return send_from_directory('static', 'diplom.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ============================================================================
# ГОЛОСИ EDGE TTS
# ============================================================================

EDGE_TTS_VOICES = [
    # Українські
    {'voice_id': 'uk-UA-OstapNeural',  'name': 'Остап',   'gender': 'male',   'language': 'uk', 'description': 'Український чоловічий'},
    {'voice_id': 'uk-UA-PolinaNeural', 'name': 'Поліна',  'gender': 'female', 'language': 'uk', 'description': 'Український жіночий'},
    # Англійські (US)
    {'voice_id': 'en-US-AriaNeural',   'name': 'Aria (US)',   'gender': 'female', 'language': 'en', 'description': 'Виразний жіночий'},
    {'voice_id': 'en-US-JennyNeural',  'name': 'Jenny (US)',  'gender': 'female', 'language': 'en', 'description': 'Дружній жіночий'},
    {'voice_id': 'en-US-EmmaNeural',   'name': 'Emma (US)',   'gender': 'female', 'language': 'en', 'description': 'Молодий жіночий'},
    {'voice_id': 'en-US-GuyNeural',    'name': 'Guy (US)',    'gender': 'male',   'language': 'en', 'description': 'Чоловічий, нейтральний'},
    {'voice_id': 'en-US-DavisNeural',  'name': 'Davis (US)',  'gender': 'male',   'language': 'en', 'description': 'Глибокий чоловічий'},
    {'voice_id': 'en-US-AndrewNeural', 'name': 'Andrew (US)', 'gender': 'male',   'language': 'en', 'description': 'Теплий чоловічий'},
    {'voice_id': 'en-US-BrianNeural',  'name': 'Brian (US)',  'gender': 'male',   'language': 'en', 'description': 'Розповідач'},
    # Англійські (UK)
    {'voice_id': 'en-GB-SoniaNeural',  'name': 'Sonia (UK)',  'gender': 'female', 'language': 'en', 'description': 'Британський жіночий'},
    {'voice_id': 'en-GB-RyanNeural',   'name': 'Ryan (UK)',   'gender': 'male',   'language': 'en', 'description': 'Британський чоловічий'},
    # Німецькі
    {'voice_id': 'de-DE-KatjaNeural',   'name': 'Katja (DE)',   'gender': 'female', 'language': 'de', 'description': 'Німецький жіночий'},
    {'voice_id': 'de-DE-ConradNeural',  'name': 'Conrad (DE)',  'gender': 'male',   'language': 'de', 'description': 'Німецький чоловічий'},
    # Французькі
    {'voice_id': 'fr-FR-DeniseNeural',  'name': 'Denise (FR)',  'gender': 'female', 'language': 'fr', 'description': 'Французький жіночий'},
    {'voice_id': 'fr-FR-HenriNeural',   'name': 'Henri (FR)',   'gender': 'male',   'language': 'fr', 'description': 'Французький чоловічий'},
    # Іспанські
    {'voice_id': 'es-ES-ElviraNeural',  'name': 'Elvira (ES)',  'gender': 'female', 'language': 'es', 'description': 'Іспанський жіночий'},
    {'voice_id': 'es-ES-AlvaroNeural',  'name': 'Alvaro (ES)',  'gender': 'male',   'language': 'es', 'description': 'Іспанський чоловічий'},
    # Італійські
    {'voice_id': 'it-IT-ElsaNeural',    'name': 'Elsa (IT)',    'gender': 'female', 'language': 'it', 'description': 'Італійський жіночий'},
    {'voice_id': 'it-IT-DiegoNeural',   'name': 'Diego (IT)',   'gender': 'male',   'language': 'it', 'description': 'Італійський чоловічий'},
    # Польські
    {'voice_id': 'pl-PL-AgnieszkaNeural', 'name': 'Agnieszka (PL)', 'gender': 'female', 'language': 'pl', 'description': 'Польський жіночий'},
    {'voice_id': 'pl-PL-MarekNeural',     'name': 'Marek (PL)',     'gender': 'male',   'language': 'pl', 'description': 'Польський чоловічий'},
    # Японські
    {'voice_id': 'ja-JP-NanamiNeural',  'name': 'Nanami (JP)',  'gender': 'female', 'language': 'ja', 'description': 'Японський жіночий'},
    {'voice_id': 'ja-JP-KeitaNeural',   'name': 'Keita (JP)',   'gender': 'male',   'language': 'ja', 'description': 'Японський чоловічий'},
    # Китайські
    {'voice_id': 'zh-CN-XiaoxiaoNeural', 'name': 'Xiaoxiao (CN)', 'gender': 'female', 'language': 'zh', 'description': 'Китайський жіночий'},
    {'voice_id': 'zh-CN-YunxiNeural',    'name': 'Yunxi (CN)',    'gender': 'male',   'language': 'zh', 'description': 'Китайський чоловічий'},
]

LANG_NAMES = {
    'uk': 'Українська', 'en': 'Англійська', 'ru': 'Російська',
    'de': 'Німецька',   'fr': 'Французька', 'es': 'Іспанська',
    'pl': 'Польська',   'it': 'Італійська', 'ja': 'Японська',
    'zh': 'Китайська',  'pt': 'Португальська', 'nl': 'Голландська',
    'tr': 'Турецька',   'ko': 'Корейська',  'ar': 'Арабська', 'hi': 'Хінді',
}

# ============================================================================
# ВИЗНАЧЕННЯ МОВИ
# ============================================================================

def detect_language(text):
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    latin    = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    chinese  = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    japanese = sum(1 for c in text if '\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF')
    arabic   = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    korean   = sum(1 for c in text if '\uAC00' <= c <= '\uD7AF')
    total = len(text)
    if total == 0: return None
    if chinese  / total > 0.3: return 'zh'
    if japanese / total > 0.2: return 'ja'
    if korean   / total > 0.3: return 'ko'
    if arabic   / total > 0.3: return 'ar'
    if cyrillic / total > 0.3:
        return 'uk' if any(c in 'ґєіїҐЄІЇ' for c in text) else 'ru'
    if latin / total > 0.5: return 'en'
    return None

# ============================================================================
# СИНТЕЗ ЧЕРЕЗ EDGE TTS
# ============================================================================

async def synthesize_edge_tts(text, voice, rate, volume, pitch):
    communicate = edge_tts.Communicate(
        text=text, voice=voice, rate=rate, volume=volume, pitch=pitch
    )
    audio_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])
    return audio_data.getvalue()

def run_edge_tts(text, voice, rate, volume, pitch):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            synthesize_edge_tts(text, voice, rate, volume, pitch)
        )
    finally:
        loop.close()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    try:
        data     = request.get_json(force=True)
        text     = data.get('text', '').strip()
        voice_id = data.get('voice_id', 'uk-UA-OstapNeural')

        if not text:
            return jsonify({'error': 'Текст не надано'}), 400
        if len(text) > 5000:
            return jsonify({'error': 'Перевищено максимум 5000 символів'}), 400

        rate_v   = data.get('rate',   0)
        volume_v = data.get('volume', 0)
        pitch_v  = data.get('pitch',  0)
        rate_str   = f"{'+' if rate_v   >= 0 else ''}{rate_v}%"
        volume_str = f"{'+' if volume_v >= 0 else ''}{volume_v}%"
        pitch_str  = f"{'+' if pitch_v  >= 0 else ''}{pitch_v}Hz"

        audio = run_edge_tts(text, voice_id, rate_str, volume_str, pitch_str)
        if not audio:
            return jsonify({'error': 'TTS не повернув аудіо. Перевірте інтернет.'}), 500

        detected_lang = detect_language(text)
        return jsonify({
            'audio_base64':   base64.b64encode(audio).decode('utf-8'),
            'audio_format':   'mp3',
            'engine':         'edge_tts',
            'detected_lang':  detected_lang,
            'detected_lang_name': LANG_NAMES.get(detected_lang),
            'audio_size_bytes': len(audio),
            'voice_id': voice_id
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/voices', methods=['GET'])
def get_voices():
    return jsonify({
        'voices': EDGE_TTS_VOICES,
        'total':  len(EDGE_TTS_VOICES),
        'engine': 'edge_tts'
    })


@app.route('/api/detect', methods=['POST'])
def detect():
    try:
        data = request.get_json(force=True)
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'Текст не надано'}), 400
        lang = detect_language(text)
        if not lang:
            return jsonify({'error': 'Не вдалося визначити мову'}), 400
        return jsonify({'detected_lang': lang, 'lang_name': LANG_NAMES.get(lang, lang.upper())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'online', 'engine': 'edge_tts', 'voices': len(EDGE_TTS_VOICES)})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
