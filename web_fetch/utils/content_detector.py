"""
Intelligent content type detection utilities.

This module provides enhanced content type detection using file signatures,
MIME type validation, content analysis, and automatic parser selection.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

from ..models.base import ContentType
from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class ContentTypeDetector:
    """Enhanced content type detector with multiple detection strategies."""
    
    def __init__(self):
        """Initialize content type detector."""
        # File signatures (magic numbers) for binary detection
        self.file_signatures = {
            # PDF
            b'%PDF': ContentType.PDF,
            
            # Images
            b'\xFF\xD8\xFF': ContentType.IMAGE,  # JPEG
            b'\x89PNG\r\n\x1a\n': ContentType.IMAGE,  # PNG
            b'GIF87a': ContentType.IMAGE,  # GIF87a
            b'GIF89a': ContentType.IMAGE,  # GIF89a
            b'RIFF': ContentType.IMAGE,  # WebP (needs further validation)
            b'BM': ContentType.IMAGE,  # BMP
            
            # Archives (treat as binary)
            b'PK\x03\x04': ContentType.RAW,  # ZIP
            b'\x1f\x8b': ContentType.RAW,  # GZIP
            b'Rar!': ContentType.RAW,  # RAR
            
            # Office documents
            b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': ContentType.RAW,  # MS Office (old)
        }
        
        # MIME type to ContentType mapping
        self.mime_type_mapping = {
            # Text types
            'text/plain': ContentType.TEXT,
            'text/html': ContentType.HTML,
            'text/xml': ContentType.XML,
            'text/css': ContentType.TEXT,
            'text/javascript': ContentType.TEXT,
            'text/csv': ContentType.CSV,
            'text/markdown': ContentType.MARKDOWN,
            
            # Application types
            'application/json': ContentType.JSON,
            'application/xml': ContentType.XML,
            'application/pdf': ContentType.PDF,
            'application/rss+xml': ContentType.RSS,
            'application/atom+xml': ContentType.RSS,
            'application/feed+json': ContentType.RSS,
            'application/ld+json': ContentType.JSON,
            'application/hal+json': ContentType.JSON,
            'application/vnd.api+json': ContentType.JSON,
            'application/csv': ContentType.CSV,
            'application/javascript': ContentType.TEXT,
            'application/ecmascript': ContentType.TEXT,
            
            # Image types
            'image/jpeg': ContentType.IMAGE,
            'image/png': ContentType.IMAGE,
            'image/gif': ContentType.IMAGE,
            'image/webp': ContentType.IMAGE,
            'image/svg+xml': ContentType.IMAGE,
            'image/bmp': ContentType.IMAGE,
            'image/tiff': ContentType.IMAGE,
            'image/x-icon': ContentType.IMAGE,
        }
        
        # URL patterns for content type hints
        self.url_patterns = {
            r'\.pdf$': ContentType.PDF,
            r'\.csv$': ContentType.CSV,
            r'\.json$': ContentType.JSON,
            r'\.xml$': ContentType.XML,
            r'\.rss$': ContentType.RSS,
            r'\.atom$': ContentType.RSS,
            r'\.feed$': ContentType.RSS,
            r'\.(jpg|jpeg|png|gif|webp|bmp|tiff|svg)$': ContentType.IMAGE,
            r'\.html?$': ContentType.HTML,
            r'\.md$': ContentType.MARKDOWN,
            r'\.txt$': ContentType.TEXT,
        }
        
        # Content patterns for text analysis
        self.content_patterns = {
            # HTML detection
            r'<!DOCTYPE\s+html': ContentType.HTML,
            r'<html[^>]*>': ContentType.HTML,
            r'<head[^>]*>': ContentType.HTML,
            r'<body[^>]*>': ContentType.HTML,
            
            # XML/RSS detection
            r'<\?xml[^>]*\?>': ContentType.XML,
            r'<rss[^>]*>': ContentType.RSS,
            r'<feed[^>]*>': ContentType.RSS,
            r'<channel[^>]*>': ContentType.RSS,
            
            # JSON detection
            r'^\s*[\{\[]': ContentType.JSON,
            
            # CSV detection (basic)
            r'^[^,\n]*,[^,\n]*,': ContentType.CSV,
        }
    
    def detect_content_type(
        self,
        content: bytes,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        filename: Optional[str] = None
    ) -> Tuple[ContentType, float]:
        """
        Detect content type using multiple strategies.
        
        Args:
            content: Content bytes to analyze
            url: Optional URL for pattern matching
            headers: Optional HTTP headers
            filename: Optional filename for extension analysis
            
        Returns:
            Tuple of (detected_content_type, confidence_score)
        """
        detections = []
        
        # Strategy 1: File signature detection (highest confidence for binary)
        signature_type, signature_confidence = self._detect_by_signature(content)
        if signature_type:
            detections.append((signature_type, signature_confidence, 'signature'))
        
        # Strategy 2: MIME type from headers (high confidence)
        if headers:
            mime_type, mime_confidence = self._detect_by_mime_type(headers)
            if mime_type:
                detections.append((mime_type, mime_confidence, 'mime'))
        
        # Strategy 3: URL pattern analysis (medium confidence)
        if url:
            url_type, url_confidence = self._detect_by_url_pattern(url)
            if url_type:
                detections.append((url_type, url_confidence, 'url'))
        
        # Strategy 4: Filename extension (medium confidence)
        if filename:
            ext_type, ext_confidence = self._detect_by_extension(filename)
            if ext_type:
                detections.append((ext_type, ext_confidence, 'extension'))
        
        # Strategy 5: Content analysis (lower confidence but broad coverage)
        content_type, content_confidence = self._detect_by_content_analysis(content)
        if content_type:
            detections.append((content_type, content_confidence, 'content'))
        
        # Strategy 6: Magic library (if available)
        if HAS_MAGIC:
            magic_type, magic_confidence = self._detect_by_magic(content)
            if magic_type:
                detections.append((magic_type, magic_confidence, 'magic'))
        
        # Combine detections and select best match
        if detections:
            return self._combine_detections(detections)
        
        # Fallback to TEXT
        return ContentType.TEXT, 0.1
    
    def _detect_by_signature(self, content: bytes) -> Tuple[Optional[ContentType], float]:
        """Detect content type by file signature (magic numbers)."""
        if len(content) < 4:
            return None, 0.0
        
        # Check signatures of different lengths
        for sig_len in [8, 4, 3, 2]:
            if len(content) >= sig_len:
                signature = content[:sig_len]
                for known_sig, content_type in self.file_signatures.items():
                    if signature.startswith(known_sig):
                        # Special case for WebP
                        if known_sig == b'RIFF' and len(content) >= 12:
                            if content[8:12] == b'WEBP':
                                return ContentType.IMAGE, 0.95
                            else:
                                continue  # Not WebP, might be other RIFF format
                        return content_type, 0.95
        
        return None, 0.0
    
    def _detect_by_mime_type(self, headers: Dict[str, str]) -> Tuple[Optional[ContentType], float]:
        """Detect content type from HTTP headers."""
        content_type_header = headers.get('content-type', '').lower()
        if not content_type_header:
            return None, 0.0
        
        # Extract main MIME type (before semicolon)
        mime_type = content_type_header.split(';')[0].strip()
        
        # Direct mapping
        if mime_type in self.mime_type_mapping:
            return self.mime_type_mapping[mime_type], 0.9
        
        # Partial matching for subtypes
        for known_mime, content_type in self.mime_type_mapping.items():
            if mime_type.startswith(known_mime.split('/')[0] + '/'):
                # Same main type, lower confidence
                return content_type, 0.7
        
        return None, 0.0
    
    def _detect_by_url_pattern(self, url: str) -> Tuple[Optional[ContentType], float]:
        """Detect content type from URL patterns."""
        url_lower = url.lower()
        
        for pattern, content_type in self.url_patterns.items():
            if re.search(pattern, url_lower, re.IGNORECASE):
                return content_type, 0.6
        
        return None, 0.0
    
    def _detect_by_extension(self, filename: str) -> Tuple[Optional[ContentType], float]:
        """Detect content type from file extension."""
        filename_lower = filename.lower()
        
        for pattern, content_type in self.url_patterns.items():
            if re.search(pattern, filename_lower, re.IGNORECASE):
                return content_type, 0.6
        
        return None, 0.0
    
    def _detect_by_content_analysis(self, content: bytes) -> Tuple[Optional[ContentType], float]:
        """Detect content type by analyzing content patterns."""
        try:
            # Try to decode as text
            text_content = content.decode('utf-8', errors='ignore')[:1000]  # First 1KB
        except Exception:
            return None, 0.0
        
        # Check for specific patterns
        for pattern, content_type in self.content_patterns.items():
            if re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE):
                return content_type, 0.5
        
        # Additional heuristics
        
        # JSON heuristic (more sophisticated)
        if self._looks_like_json(text_content):
            return ContentType.JSON, 0.6
        
        # CSV heuristic
        if self._looks_like_csv(text_content):
            return ContentType.CSV, 0.5
        
        # HTML heuristic (check for common tags)
        if self._looks_like_html(text_content):
            return ContentType.HTML, 0.4
        
        # XML heuristic
        if self._looks_like_xml(text_content):
            return ContentType.XML, 0.4
        
        return None, 0.0
    
    def _detect_by_magic(self, content: bytes) -> Tuple[Optional[ContentType], float]:
        """Detect content type using python-magic library."""
        try:
            mime_type = magic.from_buffer(content, mime=True)
            if mime_type in self.mime_type_mapping:
                return self.mime_type_mapping[mime_type], 0.8
        except Exception as e:
            logger.debug(f"Magic detection failed: {e}")
        
        return None, 0.0
    
    def _looks_like_json(self, text: str) -> bool:
        """Check if text looks like JSON."""
        text = text.strip()
        if not text:
            return False
        
        # Must start with { or [
        if not (text.startswith('{') or text.startswith('[')):
            return False
        
        # Count braces/brackets
        open_braces = text.count('{')
        close_braces = text.count('}')
        open_brackets = text.count('[')
        close_brackets = text.count(']')
        
        # Basic balance check
        return (open_braces > 0 and abs(open_braces - close_braces) <= 1) or \
               (open_brackets > 0 and abs(open_brackets - close_brackets) <= 1)
    
    def _looks_like_csv(self, text: str) -> bool:
        """Check if text looks like CSV."""
        lines = text.strip().split('\n')[:5]  # Check first 5 lines
        if len(lines) < 2:
            return False
        
        # Check for consistent comma count across lines
        comma_counts = [line.count(',') for line in lines if line.strip()]
        if not comma_counts:
            return False
        
        # All lines should have similar comma counts
        avg_commas = sum(comma_counts) / len(comma_counts)
        return avg_commas >= 1 and all(abs(count - avg_commas) <= 2 for count in comma_counts)
    
    def _looks_like_html(self, text: str) -> bool:
        """Check if text looks like HTML."""
        text_lower = text.lower()
        
        # Count HTML-like tags
        tag_count = len(re.findall(r'<[a-zA-Z][^>]*>', text_lower))
        
        # Check for common HTML elements
        html_indicators = ['<div', '<span', '<p>', '<a ', '<img', '<script', '<style']
        indicator_count = sum(1 for indicator in html_indicators if indicator in text_lower)
        
        return tag_count >= 3 or indicator_count >= 2
    
    def _looks_like_xml(self, text: str) -> bool:
        """Check if text looks like XML."""
        text = text.strip()
        
        # Check for XML declaration
        if text.startswith('<?xml'):
            return True
        
        # Check for balanced tags
        tag_pattern = r'<([a-zA-Z][^>]*)>'
        tags = re.findall(tag_pattern, text)
        
        return len(tags) >= 2 and not any(tag.lower() in ['html', 'head', 'body'] for tag in tags)
    
    def _combine_detections(self, detections: List[Tuple[ContentType, float, str]]) -> Tuple[ContentType, float]:
        """Combine multiple detection results into final decision."""
        if not detections:
            return ContentType.TEXT, 0.1
        
        # Weight different detection methods
        method_weights = {
            'signature': 1.0,  # Highest weight for binary signatures
            'magic': 0.9,     # High weight for magic library
            'mime': 0.8,      # High weight for MIME types
            'url': 0.6,       # Medium weight for URL patterns
            'extension': 0.6,  # Medium weight for extensions
            'content': 0.4,    # Lower weight for content analysis
        }
        
        # Calculate weighted scores for each content type
        type_scores = {}
        for content_type, confidence, method in detections:
            weight = method_weights.get(method, 0.5)
            weighted_score = confidence * weight
            
            if content_type in type_scores:
                # Combine scores (take maximum)
                type_scores[content_type] = max(type_scores[content_type], weighted_score)
            else:
                type_scores[content_type] = weighted_score
        
        # Select content type with highest score
        best_type = max(type_scores.items(), key=lambda x: x[1])
        return best_type[0], min(best_type[1], 1.0)
    
    def get_detection_info(
        self,
        content: bytes,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about content type detection.
        
        Returns:
            Dictionary with detection details and confidence scores
        """
        info = {
            'detected_type': None,
            'confidence': 0.0,
            'methods': {},
            'file_size': len(content),
            'is_binary': self._is_binary_content(content),
            'encoding_detected': None,
        }
        
        # Run all detection methods
        methods = [
            ('signature', lambda: self._detect_by_signature(content)),
            ('mime', lambda: self._detect_by_mime_type(headers) if headers else (None, 0.0)),
            ('url', lambda: self._detect_by_url_pattern(url) if url else (None, 0.0)),
            ('extension', lambda: self._detect_by_extension(filename) if filename else (None, 0.0)),
            ('content', lambda: self._detect_by_content_analysis(content)),
        ]
        
        if HAS_MAGIC:
            methods.append(('magic', lambda: self._detect_by_magic(content)))
        
        for method_name, method_func in methods:
            try:
                detected_type, confidence = method_func()
                info['methods'][method_name] = {
                    'type': detected_type.value if detected_type else None,
                    'confidence': confidence
                }
            except Exception as e:
                logger.debug(f"Detection method {method_name} failed: {e}")
                info['methods'][method_name] = {'type': None, 'confidence': 0.0}
        
        # Get final detection
        final_type, final_confidence = self.detect_content_type(content, url, headers, filename)
        info['detected_type'] = final_type.value
        info['confidence'] = final_confidence
        
        # Try to detect encoding for text content
        if not info['is_binary']:
            info['encoding_detected'] = self._detect_encoding(content)
        
        return info
    
    def _is_binary_content(self, content: bytes) -> bool:
        """Check if content appears to be binary."""
        if len(content) == 0:
            return False
        
        # Check for null bytes (common in binary files)
        if b'\x00' in content[:1024]:
            return True
        
        # Check for high ratio of non-printable characters
        sample = content[:1024]
        non_printable = sum(1 for byte in sample if byte < 32 and byte not in [9, 10, 13])
        ratio = non_printable / len(sample)
        
        return ratio > 0.3
    
    def _detect_encoding(self, content: bytes) -> Optional[str]:
        """Detect text encoding."""
        try:
            import chardet
            result = chardet.detect(content[:4096])  # Sample first 4KB
            return result.get('encoding')
        except ImportError:
            # Fallback encoding detection
            for encoding in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
                try:
                    content.decode(encoding)
                    return encoding
                except UnicodeDecodeError:
                    continue
        except Exception:
            pass
        
        return None
