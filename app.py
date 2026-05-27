"""
Backend системи автоматичного озвучування текстів.
Підтримує два рушії TTS:
  - Microsoft Edge TTS (безкоштовний, без обмежень)
  - ElevenLabs (показує лише голоси з "My Voices" акаунту користувача)
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import io
import base64
import asyncio
import edge_tts

app = Flask(__name__, static_folder="static", template_folder="static")
CORS(app)


# ============================================================================
# ФРОНТЕНД — роздача HTML і CSS
# ============================================================================

@app.route('/')
def index():
    return send_from_directory('static', 'diplom.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# ============================================================================
# КОНФІГУРАЦІЯ
# ============================================================================

# ElevenLabs API ключ
import os
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# Моделі ElevenLabs
TTS_MODELS = {
    'multilingual_v2': 'eleven_multilingual_v2',
    'flash_v2_5': 'eleven_flash_v2_5',
    'turbo_v2_5': 'eleven_turbo_v2_5',
}

# ============================================================================
# ГОЛОСИ EDGE TTS (безкоштовно, від Microsoft)
# ============================================================================

EDGE_TTS_VOICES = [
    # Українські
    {'voice_id': 'uk-UA-OstapNeural', 'name': 'Остап', 'gender': 'male',
     'language': 'uk', 'description': 'Український чоловічий'},
    {'voice_id': 'uk-UA-PolinaNeural', 'name': 'Поліна', 'gender': 'female',
     'language': 'uk', 'description': 'Український жіночий'},
    # Англійські (US)
    {'voice_id': 'en-US-AriaNeural', 'name': 'Aria (US)', 'gender': 'female',
     'language': 'en', 'description': 'Виразний жіночий'},
    {'voice_id': 'en-US-JennyNeural', 'name': 'Jenny (US)', 'gender': 'female',
     'language': 'en', 'description': 'Дружній жіночий'},
    {'voice_id': 'en-US-GuyNeural', 'name': 'Guy (US)', 'gender': 'male',
     'language': 'en', 'description': 'Чоловічий, нейтральний'},
    {'voice_id': 'en-US-DavisNeural', 'name': 'Davis (US)', 'gender': 'male',
     'language': 'en', 'description': 'Глибокий чоловічий'},
    {'voice_id': 'en-US-AndrewNeural', 'name': 'Andrew (US)', 'gender': 'male',
     'language': 'en', 'description': 'Теплий чоловічий'},
    {'voice_id': 'en-US-EmmaNeural', 'name': 'Emma (US)', 'gender': 'female',
     'language': 'en', 'description': 'Молодий жіночий'},
    {'voice_id': 'en-US-BrianNeural', 'name': 'Brian (US)', 'gender': 'male',
     'language': 'en', 'description': 'Розповідач'},
    # Англійські (UK)
    {'voice_id': 'en-GB-SoniaNeural', 'name': 'Sonia (UK)', 'gender': 'female',
     'language': 'en', 'description': 'Британський жіночий'},
    {'voice_id': 'en-GB-RyanNeural', 'name': 'Ryan (UK)', 'gender': 'male',
     'language': 'en', 'description': 'Британський чоловічий'},
    # Німецькі
    {'voice_id': 'de-DE-KatjaNeural', 'name': 'Katja (DE)', 'gender': 'female',
     'language': 'de', 'description': 'Німецький жіночий'},
    {'voice_id': 'de-DE-ConradNeural', 'name': 'Conrad (DE)', 'gender': 'male',
     'language': 'de', 'description': 'Німецький чоловічий'},
    # Французькі
    {'voice_id': 'fr-FR-DeniseNeural', 'name': 'Denise (FR)', 'gender': 'female',
     'language': 'fr', 'description': 'Французький жіночий'},
    {'voice_id': 'fr-FR-HenriNeural', 'name': 'Henri (FR)', 'gender': 'male',
     'language': 'fr', 'description': 'Французький чоловічий'},
    # Іспанські
    {'voice_id': 'es-ES-ElviraNeural', 'name': 'Elvira (ES)', 'gender': 'female',
     'language': 'es', 'description': 'Іспанський жіночий'},
    {'voice_id': 'es-ES-AlvaroNeural', 'name': 'Alvaro (ES)', 'gender': 'male',
     'language': 'es', 'description': 'Іспанський чоловічий'},
    # Італійські
    {'voice_id': 'it-IT-ElsaNeural', 'name': 'Elsa (IT)', 'gender': 'female',
     'language': 'it', 'description': 'Італійський жіночий'},
    {'voice_id': 'it-IT-DiegoNeural', 'name': 'Diego (IT)', 'gender': 'male',
     'language': 'it', 'description': 'Італійський чоловічий'},
    # Польські
    {'voice_id': 'pl-PL-AgnieszkaNeural', 'name': 'Agnieszka (PL)', 'gender': 'female',
     'language': 'pl', 'description': 'Польський жіночий'},
    {'voice_id': 'pl-PL-MarekNeural', 'name': 'Marek (PL)', 'gender': 'male',
     'language': 'pl', 'description': 'Польський чоловічий'},
    # Японські
    {'voice_id': 'ja-JP-NanamiNeural', 'name': 'Nanami (JP)', 'gender': 'female',
     'language': 'ja', 'description': 'Японський жіночий'},
    {'voice_id': 'ja-JP-KeitaNeural', 'name': 'Keita (JP)', 'gender': 'male',
     'language': 'ja', 'description': 'Японський чоловічий'},
    # Китайські
    {'voice_id': 'zh-CN-XiaoxiaoNeural', 'name': 'Xiaoxiao (CN)', 'gender': 'female',
     'language': 'zh', 'description': 'Китайський жіночий'},
    {'voice_id': 'zh-CN-YunxiNeural', 'name': 'Yunxi (CN)', 'gender': 'male',
     'language': 'zh', 'description': 'Китайський чоловічий'},
]


# ============================================================================
# ГОЛОСИ ELEVENLABS
# Без Aria, Charlotte, Grace, Elli, Josh, Adam, Bella, Antoni, Arnold, Matilda
# (відкинуті користувачем як платні або непридатні)
# ============================================================================

ELEVENLABS_VOICES = [
    # === Жіночі (4) ===
    {'voice_id': 'EXAVITQu4vr4xnSDxMaL', 'name': 'Sarah', 'gender': 'female',
     'description': "М'який, новинний", 'category': 'premade'},
    {'voice_id': 'FGY2WhTYpPnrIDTdsKH5', 'name': 'Laura', 'gender': 'female',
     'description': 'Теплий, для соцмереж', 'category': 'premade'},
    {'voice_id': 'cgSgspJ2msm6clMCkdW9', 'name': 'Jessica', 'gender': 'female',
     'description': 'Молодий, виразний', 'category': 'premade'},
    {'voice_id': 'pFZP5JQG7iQjIQuC4Bku', 'name': 'Lily', 'gender': 'female',
     'description': 'Теплий, для розповіді', 'category': 'premade'},

    # === Чоловічі (4) ===
    {'voice_id': 'JBFqnCBsd6RMkjVDRZzb', 'name': 'George', 'gender': 'male',
     'description': 'Теплий, британський', 'category': 'premade'},
    {'voice_id': 'nPczCjzI2devNBz1zQrb', 'name': 'Brian', 'gender': 'male',
     'description': 'Глибокий, для розповіді', 'category': 'premade'},
    {'voice_id': 'pqHfZKP75CvOlQylNhV4', 'name': 'Bill', 'gender': 'male',
     'description': 'Надійний, розповідач', 'category': 'premade'},
    {'voice_id': 'CwhRBWXzGAHq8TQ4Fs17', 'name': 'Roger', 'gender': 'male',
     'description': 'Впевнений, для соцмереж', 'category': 'premade'},
]

# ============================================================================
# ПІДТРИМУВАНІ МОВИ
# ============================================================================

LANG_NAMES = {
    'uk': 'Українська',
    'en': 'Англійська',
    'ru': 'Російська',
    'de': 'Німецька',
    'fr': 'Французька',
    'es': 'Іспанська',
    'pl': 'Польська',
    'it': 'Італійська',
    'ja': 'Японська',
    'zh': 'Китайська',
    'pt': 'Португальська',
    'nl': 'Голландська',
    'tr': 'Турецька',
    'ko': 'Корейська',
    'ar': 'Арабська',
    'hi': 'Хінді',
}


# ============================================================================
# ВИЗНАЧЕННЯ МОВИ
# ============================================================================

def detect_language(text):
    """Визначення мови за символами"""
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    latin = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    japanese = sum(1 for c in text if '\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF')
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    korean = sum(1 for c in text if '\uAC00' <= c <= '\uD7AF')

    total = len(text)
    if total == 0:
        return None

    if chinese / total > 0.3:
        return 'zh'
    if japanese / total > 0.2:
        return 'ja'
    if korean / total > 0.3:
        return 'ko'
    if arabic / total > 0.3:
        return 'ar'
    if cyrillic / total > 0.3:
        if any(c in 'ґєіїҐЄІЇ' for c in text):
            return 'uk'
        return 'ru'
    if latin / total > 0.5:
        return 'en'
    return None


# ============================================================================
# СИНТЕЗ ЧЕРЕЗ EDGE TTS
# ============================================================================

async def synthesize_edge_tts(text, voice, rate, volume, pitch):
    """Асинхронний синтез через Edge TTS"""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch
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
# ELEVENLABS — отримання саме доступних голосів
# ============================================================================

def get_user_elevenlabs_voices():
    """Повертає статичний список голосів ElevenLabs.
    Раніше тут був API-виклик, але через обмеження безкоштовного плану
    (ElevenLabs API повертає голоси, але блокує синтез з паролем 'paid_plan_required'),
    використовуємо статичний список перевірених premade-голосів."""
    if not ELEVENLABS_API_KEY:
        return [], "API-ключ не налаштовано"
    return ELEVENLABS_VOICES, None


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    """Синтез мовлення"""
    try:
        data = request.get_json(force=True)
        text = data.get('text', '').strip()
        engine = data.get('engine', 'edge_tts')
        voice_id = data.get('voice_id', 'uk-UA-OstapNeural')

        if not text:
            return jsonify({'error': 'Текст не надано'}), 400
        if len(text) > 5000:
            return jsonify({'error': 'Перевищено максимум 5000 символів'}), 400

        print(f"[{engine}] voice={voice_id}, text={text[:50]}...")
        detected_lang = detect_language(text)

        # ===== EDGE TTS =====
        if engine == 'edge_tts':
            rate_v = data.get('rate', 0)
            volume_v = data.get('volume', 0)
            pitch_v = data.get('pitch', 0)

            rate_str = f"{'+' if rate_v >= 0 else ''}{rate_v}%"
            volume_str = f"{'+' if volume_v >= 0 else ''}{volume_v}%"
            pitch_str = f"{'+' if pitch_v >= 0 else ''}{pitch_v}Hz"

            try:
                audio = run_edge_tts(text, voice_id, rate_str, volume_str, pitch_str)
                if not audio:
                    return jsonify({'error': "Edge TTS не повернув аудіо. Перевірте інтернет."}), 500

                return jsonify({
                    'audio_base64': base64.b64encode(audio).decode('utf-8'),
                    'audio_format': 'mp3',
                    'engine': 'edge_tts',
                    'detected_lang': detected_lang,
                    'detected_lang_name': LANG_NAMES.get(detected_lang),
                    'audio_size_bytes': len(audio),
                    'voice_id': voice_id
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Edge TTS: {str(e)}'}), 500

        # ===== ELEVENLABS =====
        elif engine == 'elevenlabs':
            if not ELEVENLABS_API_KEY:
                return jsonify({'error': 'ElevenLabs не налаштовано'}), 400

            model_id = data.get('model_id', TTS_MODELS['multilingual_v2'])
            stability = float(data.get('stability', 0.5))
            similarity = float(data.get('similarity_boost', 0.75))

            url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            r = requests.post(
                url,
                json=payload,
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVENLABS_API_KEY
                },
                timeout=60
            )

            if r.status_code != 200:
                try:
                    err = r.json()
                    detail = err.get('detail', {})
                    msg = detail.get('message', 'Помилка ElevenLabs') if isinstance(detail, dict) else str(detail)
                except Exception:
                    msg = r.text or f'HTTP {r.status_code}'
                return jsonify({'error': msg}), 400

            return jsonify({
                'audio_base64': base64.b64encode(r.content).decode('utf-8'),
                'audio_format': 'mp3',
                'engine': 'elevenlabs',
                'detected_lang': detected_lang,
                'detected_lang_name': LANG_NAMES.get(detected_lang),
                'audio_size_bytes': len(r.content),
                'voice_id': voice_id
            })

        else:
            return jsonify({'error': f'Невідомий рушій: {engine}'}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Список голосів"""
    engine = request.args.get('engine', 'edge_tts')

    if engine == 'edge_tts':
        return jsonify({
            'voices': EDGE_TTS_VOICES,
            'total': len(EDGE_TTS_VOICES),
            'engine': 'edge_tts'
        })

    elif engine == 'elevenlabs':
        voices, error = get_user_elevenlabs_voices()
        return jsonify({
            'voices': voices,
            'total': len(voices),
            'engine': 'elevenlabs',
            'error': error,
            'instructions': {
                'message': 'У безкоштовному плані ElevenLabs API працює тільки з тими '
                           'голосами, які ви додали в "My Voices" через веб-сайт.',
                'steps': [
                    'Зайдіть на https://elevenlabs.io/app/voice-library',
                    'Знайдіть голоси, які вам подобаються',
                    'Натисніть "Add to VoiceLab" для кожного (макс. 3 на free tier)',
                    'Поверніться у застосунок та натисніть "Оновити"'
                ]
            } if not voices else None
        })
    else:
        return jsonify({'error': f'Невідомий рушій: {engine}'}), 400


@app.route('/api/elevenlabs/info', methods=['GET'])
def elevenlabs_info():
    """Інформація про підписку ElevenLabs"""
    if not ELEVENLABS_API_KEY:
        return jsonify({'configured': False, 'error': 'API-ключ не налаштовано'}), 400

    try:
        r = requests.get(
            f"{ELEVENLABS_API_URL}/user/subscription",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10
        )
        if r.status_code == 200:
            sub = r.json()
            return jsonify({
                'configured': True,
                'tier': sub.get('tier', 'free'),
                'character_count': sub.get('character_count', 0),
                'character_limit': sub.get('character_limit', 0),
                'voice_limit': sub.get('voice_limit', 0)
            })
        return jsonify({'configured': True, 'error': f'HTTP {r.status_code}'}), 400
    except Exception as e:
        return jsonify({'configured': True, 'error': str(e)}), 500


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
        return jsonify({
            'detected_lang': lang,
            'lang_name': LANG_NAMES.get(lang, lang.upper()),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'online',
        'engines': {
            'edge_tts': True,
            'elevenlabs': bool(ELEVENLABS_API_KEY)
        },
        'edge_tts_voices': len(EDGE_TTS_VOICES)
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
