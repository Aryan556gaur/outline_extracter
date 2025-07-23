import os
import json
import logging
from pdf_processor import process_pdf

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

INPUT_DIR = "input"
OUTPUT_DIR = "output"

def main():

    INPUT_DIR = "input"
    OUTPUT_DIR = "output"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logging.warning(f"No PDF files found in {INPUT_DIR}. Exiting.")
        return

    logging.info(f"Found {len(pdf_files)} PDF files to process.")

    for pdf_file in pdf_files:
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        output_filename = os.path.splitext(pdf_file)[0] + ".json"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        result = process_pdf(pdf_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logging.info(f"Output saved to {output_path}")

if __name__ == "__main__":
    main()