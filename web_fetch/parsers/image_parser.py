"""
Image metadata extraction and processing.

This module provides functionality to extract metadata from images including
EXIF data, dimensions, format information, and alt text from HTML context.
"""

from __future__ import annotations

import io
import logging
from typing import Optional, Dict, Any, Tuple

try:
    from PIL import Image, ExifTags
    from PIL.ExifTags import TAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from ..models.base import ImageMetadata
from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class ImageParser:
    """Parser for extracting metadata from images."""
    
    def __init__(self):
        """Initialize image parser."""
        if not HAS_PIL:
            raise ImportError("Pillow is required for image parsing. Install with: pip install Pillow")
    
    def parse(
        self, 
        content: bytes, 
        url: Optional[str] = None, 
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[Dict[str, Any], ImageMetadata]:
        """
        Parse image content and extract metadata.
        
        Args:
            content: Image file content as bytes
            url: Optional URL for context in error messages
            headers: Optional HTTP headers for additional context
            
        Returns:
            Tuple of (image_data_dict, image_metadata)
            
        Raises:
            ContentError: If image parsing fails
        """
        try:
            # Create a BytesIO object from the content
            image_stream = io.BytesIO(content)
            
            # Open image with PIL
            with Image.open(image_stream) as img:
                # Extract basic metadata
                metadata = self._extract_metadata(img, len(content))
                
                # Extract EXIF data if available
                exif_data = self._extract_exif_data(img)
                metadata.exif_data = exif_data
                
                # Create image data dictionary
                image_data = {
                    'format': metadata.format,
                    'mode': metadata.mode,
                    'size': (metadata.width, metadata.height),
                    'has_transparency': metadata.has_transparency,
                    'file_size': metadata.file_size,
                    'color_space': metadata.color_space,
                    'dpi': metadata.dpi,
                    'exif_summary': self._get_exif_summary(exif_data)
                }
                
                return image_data, metadata
                
        except Exception as e:
            logger.error(f"Failed to parse image from {url}: {e}")
            raise ContentError(f"Invalid or corrupted image file: {e}")
    
    def _extract_metadata(self, img: Image.Image, file_size: int) -> ImageMetadata:
        """Extract basic metadata from PIL Image object."""
        metadata = ImageMetadata()
        
        metadata.format = img.format
        metadata.mode = img.mode
        metadata.width, metadata.height = img.size
        metadata.file_size = file_size
        
        # Check for transparency
        metadata.has_transparency = (
            img.mode in ('RGBA', 'LA') or 
            (img.mode == 'P' and 'transparency' in img.info)
        )
        
        # Get DPI information
        if hasattr(img, 'info') and 'dpi' in img.info:
            metadata.dpi = img.info['dpi']
        
        # Determine color space
        if img.mode == 'RGB':
            metadata.color_space = 'RGB'
        elif img.mode == 'RGBA':
            metadata.color_space = 'RGBA'
        elif img.mode == 'CMYK':
            metadata.color_space = 'CMYK'
        elif img.mode == 'L':
            metadata.color_space = 'Grayscale'
        elif img.mode == 'P':
            metadata.color_space = 'Palette'
        else:
            metadata.color_space = img.mode
        
        return metadata
    
    def _extract_exif_data(self, img: Image.Image) -> Dict[str, Any]:
        """Extract EXIF data from image."""
        exif_data = {}
        
        try:
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = img._getexif()
                
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Convert bytes to string for text fields
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except UnicodeDecodeError:
                            value = str(value)
                    
                    exif_data[tag] = value
                    
        except Exception as e:
            logger.warning(f"Failed to extract EXIF data: {e}")
        
        return exif_data
    
    def _get_exif_summary(self, exif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of important EXIF data."""
        summary = {}
        
        # Common EXIF fields to extract
        important_fields = {
            'DateTime': 'date_taken',
            'Make': 'camera_make',
            'Model': 'camera_model',
            'Software': 'software',
            'Artist': 'artist',
            'Copyright': 'copyright',
            'ImageDescription': 'description',
            'Orientation': 'orientation',
            'XResolution': 'x_resolution',
            'YResolution': 'y_resolution',
            'ResolutionUnit': 'resolution_unit',
            'Flash': 'flash',
            'FocalLength': 'focal_length',
            'ExposureTime': 'exposure_time',
            'FNumber': 'f_number',
            'ISO': 'iso',
            'WhiteBalance': 'white_balance',
            'GPS GPSLatitude': 'gps_latitude',
            'GPS GPSLongitude': 'gps_longitude',
        }
        
        for exif_key, summary_key in important_fields.items():
            if exif_key in exif_data:
                summary[summary_key] = exif_data[exif_key]
        
        return summary
    
    def get_image_info(self, content: bytes) -> Dict[str, Any]:
        """
        Get basic image information without full parsing.
        
        Args:
            content: Image file content as bytes
            
        Returns:
            Dictionary with basic image information
            
        Raises:
            ContentError: If image reading fails
        """
        try:
            image_stream = io.BytesIO(content)
            
            with Image.open(image_stream) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.size[0],
                    'height': img.size[1],
                    'file_size': len(content)
                }
                
        except Exception as e:
            raise ContentError(f"Failed to read image: {e}")
    
    def is_valid_image(self, content: bytes) -> bool:
        """
        Check if content is a valid image.
        
        Args:
            content: Content to check as bytes
            
        Returns:
            True if content is a valid image, False otherwise
        """
        try:
            image_stream = io.BytesIO(content)
            with Image.open(image_stream) as img:
                img.verify()  # Verify the image
            return True
        except Exception:
            return False
    
    def get_thumbnail(self, content: bytes, size: Tuple[int, int] = (128, 128)) -> bytes:
        """
        Generate a thumbnail of the image.
        
        Args:
            content: Original image content as bytes
            size: Thumbnail size as (width, height) tuple
            
        Returns:
            Thumbnail image as bytes
            
        Raises:
            ContentError: If thumbnail generation fails
        """
        try:
            image_stream = io.BytesIO(content)
            
            with Image.open(image_stream) as img:
                # Create thumbnail
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save thumbnail to bytes
                thumbnail_stream = io.BytesIO()
                img.save(thumbnail_stream, format='JPEG', quality=85)
                thumbnail_stream.seek(0)
                
                return thumbnail_stream.getvalue()
                
        except Exception as e:
            raise ContentError(f"Failed to generate thumbnail: {e}")
