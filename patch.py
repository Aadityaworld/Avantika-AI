import os, re

with open('audio.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"en-US-AriaNeural"', '"en-IN-NeerjaNeural"')

new_custom = '''
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
'''

content = re.sub(r'CUSTOM_MODEL_PATH.*?(?=def _capture_query_after_wake)', new_custom, content, flags=re.DOTALL)
content = content.replace('active_key = WAKE_KEY if os.path.exists(CUSTOM_MODEL_PATH) else "hey_jarvis"', 'active_key = WAKE_KEY if os.path.exists(CUSTOM_MODEL_PATH) or os.path.exists(LEGACY_MODEL_PATH) else "hey_jarvis"')
content = content.replace('active_threshold = WAKE_THRESHOLD if os.path.exists(CUSTOM_MODEL_PATH) else 0.5', 'active_threshold = WAKE_THRESHOLD if os.path.exists(CUSTOM_MODEL_PATH) or os.path.exists(LEGACY_MODEL_PATH) else 0.5')

with open('audio.py', 'w', encoding='utf-8') as f:
    f.write(content)
