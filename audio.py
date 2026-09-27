"""Audio input and output module — edge-tts neural synthesis + pygame playback."""

import asyncio
import logging
import math
import os
import tempfile
import threading
import time
from typing import Callable, Optional

import edge_tts
import pygame
import speech_recognition as sr
import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model

logger = logging.getLogger(__name__)

# ── Optional faster-whisper ───────────────────────────────────────────────────
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

# ── Module state ──────────────────────────────────────────────────────────────
_tts_lock = threading.Lock()
_recognizer = sr.Recognizer()
_is_speaking = threading.Event()

# Neural voice default
_TTS_VOICE: str = "en-IN-NeerjaNeural"

# Runtime-adjustable settings stored as WPM / 0-1 float
_tts_rate: int = 175          # words-per-minute baseline (maps to edge-tts +N%)
_tts_volume: float = 0.9      # 0.0–1.0 (maps to edge-tts +N% / -N%)

# ── pygame mixer — lazy singleton init ───────────────────────────────────────
_mixer_ready: bool = False
_mixer_lock = threading.Lock()


def _ensure_mixer() -> None:
    """Initialise pygame.mixer exactly once, thread-safely."""
    global _mixer_ready
    if _mixer_ready:
        return
    with _mixer_lock:
        if not _mixer_ready:
            pygame.mixer.init()
            _mixer_ready = True


# ── TTS rate/volume → edge-tts format converters ─────────────────────────────

def _rate_to_edgetts(wpm: int) -> str:
    """Map WPM (60–400) to edge-tts rate string relative to ~150 WPM baseline."""
    # edge-tts baseline ≈ 150 WPM → derive percent delta
    pct = round((wpm - 150) / 150 * 100)
    return f"{pct:+d}%"


def _volume_to_edgetts(vol: float) -> str:
    """Map 0.0–1.0 to edge-tts volume string (0 → -100%, 1.0 → +0%)."""
    pct = round((vol - 1.0) * 100)   # 1.0 → 0%, 0.5 → -50%, 0.0 → -100%
    return f"{pct:+d}%"


# ── Public settings setters ───────────────────────────────────────────────────

def set_speech_rate(rate: int) -> None:
    """Update module-level TTS speech rate (words per minute)."""
    global _tts_rate
    _tts_rate = max(60, min(400, int(rate)))
    logger.info("TTS rate updated to %d WPM (%s)", _tts_rate, _rate_to_edgetts(_tts_rate))


def set_speech_volume(volume: float) -> None:
    """Update module-level TTS volume (0.0–1.0)."""
    global _tts_volume
    _tts_volume = max(0.0, min(1.0, float(volume)))
    logger.info("TTS volume updated to %.2f (%s)", _tts_volume, _volume_to_edgetts(_tts_volume))


def is_speaking() -> bool:
    """Return True while TTS playback is active (mic echo suppression guard)."""
    return _is_speaking.is_set()


# ── Neural speech synthesis ───────────────────────────────────────────────────

async def _synthesise(text: str, path: str) -> None:
    """Async edge-tts synthesis to MP3 file."""
    comm = edge_tts.Communicate(
        text,
        _TTS_VOICE,
        rate=_rate_to_edgetts(_tts_rate),
        volume=_volume_to_edgetts(_tts_volume),
    )
    await comm.save(path)


_interrupt_speech = threading.Event()

def stop_playback() -> bool:
    """Halt audio playback immediately."""
    _interrupt_speech.set()
    with _tts_lock:
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
    _is_speaking.clear()
    return True

def _barge_in_listener():
    """Background thread to listen for 'stop' commands during playback."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            while _is_speaking.is_set() and not _interrupt_speech.is_set():
                try:
                    # Listen in very short chunks so we can exit cleanly
                    audio_data = recognizer.listen(source, timeout=0.5, phrase_time_limit=2)
                    text = recognizer.recognize_google(audio_data).lower()
                    if any(w in text for w in ["stop", "quiet", "pause", "shut up"]):
                        logger.info("Barge-in command detected: '%s'", text)
                        stop_playback()
                        break
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Barge-in listener failed to bind mic: %s", e)

def speak(text: str) -> None:
    """Synthesize and play neural TTS speech; block mic while playing."""
    clean_text = text.strip()
    if not clean_text:
        return

    _ensure_mixer()
    _is_speaking.set()
    _interrupt_speech.clear()

    # Start barge-in monitor
    threading.Thread(target=_barge_in_listener, daemon=True, name="BargeInThread").start()

    tmp_path = os.path.join(tempfile.gettempdir(), "edge_tts_out.mp3")
    with _tts_lock:
        try:
            # Generate MP3 via edge-tts
            asyncio.run(_synthesise(clean_text, tmp_path))

            if _interrupt_speech.is_set():
                return

            # Play via pygame.mixer
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            # Block until playback finishes or interrupted
            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy() and not _interrupt_speech.is_set():
                clock.tick(50)  # Polling at 20ms intervals

        except Exception as e:
            logger.error("edge-tts / pygame TTS failure: %s", e)
        finally:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            # Cooldown prevents mic picking up echo decay
            time.sleep(0.3)
            _is_speaking.clear()



def transcribe_with_whisper(audio_bytes: bytes, model_size: str = "base") -> str:
    """Hook for faster-whisper STT with VAD filtering against acoustic hallucination."""
    if not FASTER_WHISPER_AVAILABLE:
        raise NotImplementedError("faster-whisper is not installed.")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        audio_bytes,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        no_speech_threshold=0.6,
    )
    return " ".join(seg.text for seg in segments).strip()


def listen_command(timeout: int = 5, phrase_time_limit: int = 8) -> str:
    """Single-shot listening for audio from microphone with wake-word strip."""
    if is_speaking():
        return ""

    command = ""
    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = _recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
            text = _recognizer.recognize_google(audio)
            command = text.lower().strip()
            if "alexa" in command:
                command = command.replace("alexa", "").strip()

    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        logger.warning("Speech recognition request error: %s", e)
        return ""
    except Exception as e:
        logger.error("Microphone hardware error: %s", e)
        return ""

    return command


def _rms_normalized(audio: sr.AudioData) -> float:
    """Compute RMS amplitude of raw audio, normalized 0.0–1.0."""
    try:
        raw = audio.frame_data
        # 16-bit signed samples → parse as short integers
        n = len(raw) // 2
        if n == 0:
            return 0.0
        total = sum(
            int.from_bytes(raw[i * 2: i * 2 + 2], "little", signed=True) ** 2
            for i in range(min(n, 4096))   # cap iterations for performance
        )
        rms = math.sqrt(total / min(n, 4096))
        # Normalize: 16-bit max ≈ 32767
        return min(1.0, rms / 32767.0 * 8.0)   # ×8 boosts quiet speech into visible range
    except Exception:
        return 0.0



CUSTOM_MODEL_PATH = os.path.join(os.path.dirname(__file__), "avantika.onnx")
LEGACY_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hey_assistant.onnx")
WAKE_KEY = "avantika"
WAKE_THRESHOLD = 0.55

def _init_wakeword_model() -> Model:
    """Initialize openwakeword ONNX model."""
    if os.path.exists(CUSTOM_MODEL_PATH):
        logger.info("Loaded custom wake-word model from %s", CUSTOM_MODEL_PATH)
        return Model(wakeword_models=[CUSTOM_MODEL_PATH], inference_framework="onnx")
    elif os.path.exists(LEGACY_MODEL_PATH):
        logger.info("Loaded legacy wake-word model from %s", LEGACY_MODEL_PATH)
        return Model(wakeword_models=[LEGACY_MODEL_PATH], inference_framework="onnx")
    else:
        logger.warning("Custom model not found, falling back to 'hey_jarvis'")
        openwakeword.utils.download_models() # ensure model exists
        return Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
def _capture_query_after_wake() -> str:
    """Single-shot listener after wakeword detection."""
    if is_speaking():
        return ""
    command = ""
    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = _recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=8,
            )
            text = _recognizer.recognize_google(audio)
            command = text.lower().strip()
    except Exception as e:
        logger.warning("Failed to capture command after wake: %s", e)
    return command

def start_wakeword_listener(
    on_wake_callback: Callable[[], None],
    on_command_captured: Callable[[str], None],
    level_callback: Optional[Callable[[float], None]] = None,
    stop_event: Optional[threading.Event] = None,
) -> threading.Thread:
    """Run persistent non-blocking openwakeword detector in a daemon thread."""
    def _listener_loop() -> None:
        logger.info("Initializing openwakeword model...")
        try:
            oww_model = _init_wakeword_model()
        except Exception as e:
            logger.error("Failed to load openwakeword model: %s", e)
            return

        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1280

        audio_sys = pyaudio.PyAudio()
        try:
            mic_stream = audio_sys.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        except Exception as e:
            logger.error("PyAudio failed to open stream: %s", e)
            audio_sys.terminate()
            return

        logger.info("Wakeword listener started. Waiting for 'hey_jarvis'...")

        while not (stop_event and stop_event.is_set()):
            if is_speaking():
                if level_callback:
                    level_callback(0.0)
                time.sleep(0.2)
                continue

            try:
                # Read raw audio block from mic
                data = mic_stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)

                # Compute RMS for meter callback
                if level_callback:
                    if len(audio_data) > 0:
                        # RMS amplitude
                        total = np.sum(audio_data.astype(np.float32) ** 2)
                        rms = math.sqrt(total / len(audio_data))
                        level_callback(min(1.0, rms / 32767.0 * 8.0))
                    else:
                        level_callback(0.0)

                # Feed audio to openwakeword prediction
                prediction = oww_model.predict(audio_data)
                
                # Determine active wake key and threshold
                active_key = WAKE_KEY if os.path.exists(CUSTOM_MODEL_PATH) or os.path.exists(LEGACY_MODEL_PATH) else "hey_jarvis"
                active_threshold = WAKE_THRESHOLD if os.path.exists(CUSTOM_MODEL_PATH) or os.path.exists(LEGACY_MODEL_PATH) else 0.5

                # Check for trigger
                # Note: For custom models, prediction keys often include version tags if not named strictly.
                # To be safe, we check if any key in prediction contains the active_key.
                score = 0.0
                for k, v in prediction.items():
                    if active_key in k:
                        score = max(score, v)
                
                if score > active_threshold:
                    logger.info("Wakeword detected! (score: %.2f)", score)
                    on_wake_callback()
                    
                    # Stop pyAudio stream temporarily so SpeechRecognition can bind to the mic
                    mic_stream.stop_stream()
                    
                    cmd = _capture_query_after_wake()
                    if cmd:
                        on_command_captured(cmd)
                        
                    # Resume continuous stream and reset buffer
                    mic_stream.start_stream()
                    oww_model.reset()

            except Exception as e:
                logger.error("Wakeword loop error: %s", e)
                if level_callback:
                    level_callback(0.0)
                time.sleep(1)

        mic_stream.stop_stream()
        mic_stream.close()
        audio_sys.terminate()

    thread = threading.Thread(target=_listener_loop, daemon=True, name="WakewordListenerThread")
    thread.start()
    return thread
