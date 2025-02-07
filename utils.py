import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename
from config import Config

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def generate_order_number():
    return f"DTF-{uuid.uuid4().hex[:8].upper()}"

def calculate_cost(width_inches, height_inches):
    area = width_inches * height_inches
    return area * Config.COST_PER_SQINCH

def get_image_dimensions(file_path):
    with Image.open(file_path) as img:
        width_px, height_px = img.size
        # Convert pixels to inches (assuming 300 DPI for DTF printing)
        width_inches = width_px / 300
        height_inches = height_px / 300
        return width_inches, height_inches

def validate_image(file_path):
    try:
        with Image.open(file_path) as img:
            if img.format != 'PNG':
                return False, "Only PNG files are supported"
            if img.mode not in ('RGB', 'RGBA'):
                return False, "Image must be in RGB or RGBA format"
            width, height = img.size
            if width > 4800 or height > 4800:  # Max 16" at 300 DPI
                return False, "Image dimensions too large"
            return True, "Image is valid"
    except Exception as e:
        return False, f"Error validating image: {str(e)}"