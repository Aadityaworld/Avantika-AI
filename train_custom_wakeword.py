import os
from openwakeword.data import generate_adversarial_texts
from openwakeword.model import Model
from openwakeword.train import train_model

TARGET_PHRASE = "hey assistant"
MODEL_NAME = "hey_assistant"
OUTPUT_DIR = "./trained_models"

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating synthetic training pipeline for: '{TARGET_PHRASE}'...")

    # 1. Generate phonetically similar adversarial negative examples
    # (Prevents false triggers from words like "assistant", "system", etc.)
    adversarial_phrases = generate_adversarial_texts(
        TARGET_PHRASE,
        n_samples=50
    )
    print("Adversarial phrases generated:", adversarial_phrases[:5])

    # 2. Run automated training pipeline
    # Trains the classification head and exports directly to ONNX
    train_model(
        target_words=[TARGET_PHRASE],
        adversarial_words=adversarial_phrases,
        n_samples=3000,
        steps=15000,
        output_dir=OUTPUT_DIR,
        model_name=MODEL_NAME,
    )
    print(f"Model generated successfully: {OUTPUT_DIR}/{MODEL_NAME}.onnx")

if __name__ == "__main__":
    main()
