import os
from sentence_transformers import SentenceTransformer

# Define the directory to save models
MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# Define the models to download
# For Round 1A, these models are not strictly necessary as outline extraction
# primarily relies on PyMuPDF and PDFMiner.six.
# They are included here for consistency with a potential full solution setup.
MODELS_TO_DOWNLOAD = [
    "all-MiniLM-L6-v2",
    # "sentence-transformers/multilingual-e5-small" # Uncomment for multilingual support
]

def download_and_save_model(model_name):
    """Downloads a SentenceTransformer model and saves it locally."""
    model_path = os.path.join(MODEL_DIR, model_name.replace("/", "_"))
    if not os.path.exists(model_path):
        print(f"Downloading model: {model_name} to {model_path}...")
        try:
            # The from_pretrained method handles downloading and saving
            model = SentenceTransformer(model_name)
            model.save(model_path)
            print(f"Successfully downloaded and saved {model_name}.")
        except Exception as e:
            print(f"Error downloading {model_name}: {e}")
    else:
        print(f"Model {model_name} already exists at {model_path}.")

if __name__ == "__main__":
    for model_name in MODELS_TO_DOWNLOAD:
        download_and_save_model(model_name)
    print("Model download process completed.")
