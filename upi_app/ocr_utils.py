import pytesseract
from PIL import Image
import os
import re

# IMPORTANT: Set this to your Tesseract-OCR installation path if not in PATH
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def verify_document(image_path, expected_name, expected_reg_no):
    """
    Analyzes an image to find the expected business name and registration number.
    Returns: (score, notes, extracted_text_snippet)
    """
    try:
        if not os.path.exists(image_path):
             return 0.0, "File not found.", ""

        # Open image
        img = Image.open(image_path)
        
        # specific Tesseract config can be added here
        # plain text extraction
        text = pytesseract.image_to_string(img)
        
        score = 0.0
        notes = []
        
        # Clean text for comparison
        text_lower = text.lower()
        
        if not text.strip():
             return 0.0, "OCR returned empty text. Image might be unclear.", ""

        # 1. Check Keywords (Is it a license?)
        keywords = ['license', 'registration', 'certificate', 'govt', 'government', 'india', 'ministry']
        keyword_hits = sum(1 for k in keywords if k in text_lower)
        if keyword_hits > 0:
            score += 20.0
            notes.append(f"Found {keyword_hits} official keywords.")
        
        # 2. Check Name Match
        if expected_name and expected_name.lower() in text_lower:
            score += 40.0
            notes.append("Business Name matched.")
        else:
             # Fuzzy match or partial match could be added here
             pass

        # 3. Check Registration Number Match
        # Remove spaces/dashes for better matching
        clean_text = re.sub(r'[^a-zA-Z0-9]', '', text_lower)
        clean_reg = re.sub(r'[^a-zA-Z0-9]', '', expected_reg_no.lower()) if expected_reg_no else ""
        
        if clean_reg and clean_reg in clean_text:
            score += 40.0
            notes.append("Registration Number matched.")
        
        return score, notes, text[:100] + "..."

    except pytesseract.TesseractNotFoundError:
        return 0.0, "Server Error: Tesseract-OCR not installed on server.", ""
    except Exception as e:
        return 0.0, f"OCR Error: {str(e)}", ""
