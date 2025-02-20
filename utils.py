import os
import uuid
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Disable decompression bomb protection
from werkzeug.utils import secure_filename
from config import Config
from io import BytesIO
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def generate_order_number():
    return f"DTF-{uuid.uuid4().hex[:8].upper()}"

def get_display_value(actual: float) -> str:
    """Round to 2 decimals for display using proper rounding"""
    display_decimal = Decimal(str(actual)).quantize(
        Decimal('0.01'), 
        rounding=ROUND_HALF_UP
    )
    return f"{display_decimal:.2f}"

def price_round(d: Decimal) -> int:
    """Round to nearest whole number, rounding .5 up"""
    return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def calculate_cost(width_inches, height_inches):
    """Calculate cost using precise decimal arithmetic"""
    # Convert inputs to Decimal and round to 2 decimal places for calculation
    width_dec = Decimal(str(width_inches)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    height_dec = Decimal(str(height_inches)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Round dimensions up at .5 for pricing
    width_rounded = price_round(width_dec)
    height_rounded = price_round(height_dec)
    
    # Calculate area and cost
    area = Decimal(width_rounded * height_rounded)
    cost = area * Decimal(str(Config.COST_PER_SQINCH))
    
    logger.debug(f"Cost calculation:")
    logger.debug(f"Input dimensions: {width_inches} x {height_inches}")
    logger.debug(f"Decimal dimensions: {width_dec} x {height_dec}")
    logger.debug(f"Rounded dimensions: {width_rounded} x {height_rounded}")
    logger.debug(f"Area: {area} sq inches")
    logger.debug(f"Final cost: ${cost:.2f}")
    
    return float(cost)

def get_image_dimensions(file_data):
    with Image.open(file_data) as img:
        # Get physical size in inches using the image's DPI info
        dpi_x, dpi_y = img.info.get('dpi', (96, 96))  # Default to 96 DPI if not specified
        
        # Convert to Decimal for precise calculations
        width_px = Decimal(str(img.size[0]))
        height_px = Decimal(str(img.size[1]))
        dpi_x = Decimal(str(dpi_x))
        dpi_y = Decimal(str(dpi_y))
        
        # Calculate dimensions with 2 decimal places precision
        width_inches = (width_px / dpi_x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        height_inches = (height_px / dpi_y).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.debug(f"Image dimensions calculation:")
        logger.debug(f"Pixels: {width_px} x {height_px}")
        logger.debug(f"DPI: {dpi_x} x {dpi_y}")
        logger.debug(f"Result inches: {width_inches} x {height_inches}")
        
        # Return as float but maintain precision
        return float(width_inches), float(height_inches)

def validate_image(file_data):
    try:
        with Image.open(file_data) as img:
            if img.format != 'PNG':
                return False, "Only PNG files are supported"
            if img.mode not in ('RGB', 'RGBA'):
                return False, "Image must be in RGB or RGBA format"
            
            # Get physical dimensions
            dpi_x, dpi_y = img.info.get('dpi', (96, 96))
            width_inches = img.size[0] / dpi_x
            height_inches = img.size[1] / dpi_y
            
            # Log the dimensions for debugging
            logger.debug(f"Image physical dimensions: {width_inches:.2f}\" x {height_inches:.2f}\"")
            
            # Check if either dimension exceeds 22 inches
            if width_inches > 22 or height_inches > 22:
                return False, f"Image dimensions ({width_inches:.1f}\" x {height_inches:.1f}\") exceed maximum of 22 inches"
                
            return True, "Image is valid"
    except Exception as e:
        return False, f"Error validating image: {str(e)}"

def generate_thumbnail(image_data, max_size=(100, 100)):
    """Generate a lightweight thumbnail from image data"""
    try:
        img = Image.open(BytesIO(image_data))

        # Keep original mode (RGBA or RGB)
        if img.mode not in ('RGBA', 'RGB'):
            img = img.convert('RGBA')

        # Calculate thumbnail size while maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save thumbnail as PNG to preserve transparency
        thumb_io = BytesIO()
        img.save(thumb_io, 'PNG', optimize=True)
        thumb_io.seek(0)

        return thumb_io.getvalue()
    except Exception as e:
        logger.error(f"Error generating thumbnail: {str(e)}")
        return None

def get_thumbnail_key(file_key):
    """Generate the storage key for a thumbnail"""
    name, ext = os.path.splitext(file_key)
    return f"{name}-min.png"