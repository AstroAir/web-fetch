"""
PDF content extraction and metadata parsing.

This module provides functionality to extract text content and metadata from PDF documents
using PyPDF2, with fallback handling for encrypted or corrupted files.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

from ..models.base import PDFMetadata
from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class PDFParser:
    """Parser for extracting content and metadata from PDF documents."""
    
    def __init__(self):
        """Initialize PDF parser."""
        if not HAS_PYPDF2:
            raise ImportError("PyPDF2 is required for PDF parsing. Install with: pip install PyPDF2")
    
    def parse(self, content: bytes, url: Optional[str] = None) -> Tuple[str, PDFMetadata]:
        """
        Parse PDF content and extract text and metadata.
        
        Args:
            content: PDF file content as bytes
            url: Optional URL for context in error messages
            
        Returns:
            Tuple of (extracted_text, pdf_metadata)
            
        Raises:
            ContentError: If PDF parsing fails
        """
        try:
            # Create a BytesIO object from the content
            pdf_stream = io.BytesIO(content)
            
            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            # Check if PDF is encrypted
            is_encrypted = pdf_reader.is_encrypted
            if is_encrypted:
                # Try to decrypt with empty password
                try:
                    pdf_reader.decrypt("")
                except Exception as e:
                    logger.warning(f"Failed to decrypt PDF from {url}: {e}")
                    raise ContentError(f"PDF is encrypted and cannot be decrypted: {e}")
            
            # Extract metadata
            metadata = self._extract_metadata(pdf_reader)
            metadata.encrypted = is_encrypted
            metadata.page_count = len(pdf_reader.pages)
            
            # Extract text from all pages
            extracted_text = self._extract_text(pdf_reader)
            metadata.text_length = len(extracted_text)
            
            return extracted_text, metadata
            
        except PyPDF2.errors.PdfReadError as e:
            logger.error(f"Failed to read PDF from {url}: {e}")
            raise ContentError(f"Invalid or corrupted PDF file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing PDF from {url}: {e}")
            raise ContentError(f"Failed to parse PDF: {e}")
    
    def _extract_metadata(self, pdf_reader: PyPDF2.PdfReader) -> PDFMetadata:
        """Extract metadata from PDF reader."""
        metadata = PDFMetadata()
        
        try:
            if pdf_reader.metadata:
                # Extract standard metadata fields
                metadata.title = self._clean_metadata_value(pdf_reader.metadata.get('/Title'))
                metadata.author = self._clean_metadata_value(pdf_reader.metadata.get('/Author'))
                metadata.subject = self._clean_metadata_value(pdf_reader.metadata.get('/Subject'))
                metadata.creator = self._clean_metadata_value(pdf_reader.metadata.get('/Creator'))
                metadata.producer = self._clean_metadata_value(pdf_reader.metadata.get('/Producer'))
                
                # Extract dates
                creation_date = pdf_reader.metadata.get('/CreationDate')
                if creation_date:
                    metadata.creation_date = self._parse_pdf_date(creation_date)
                
                modification_date = pdf_reader.metadata.get('/ModDate')
                if modification_date:
                    metadata.modification_date = self._parse_pdf_date(modification_date)
                
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")
        
        return metadata
    
    def _extract_text(self, pdf_reader: PyPDF2.PdfReader) -> str:
        """Extract text from all pages of the PDF."""
        text_parts = []
        
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                continue
        
        return "\n\n".join(text_parts)
    
    def _clean_metadata_value(self, value: Any) -> Optional[str]:
        """Clean and normalize metadata values."""
        if value is None:
            return None
        
        # Convert to string and clean up
        str_value = str(value).strip()
        
        # Remove common PDF metadata artifacts
        if str_value.startswith('(') and str_value.endswith(')'):
            str_value = str_value[1:-1]
        
        # Remove null bytes and other control characters
        str_value = ''.join(char for char in str_value if ord(char) >= 32 or char in '\n\r\t')
        
        return str_value if str_value else None
    
    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """Parse PDF date string to datetime object."""
        if not date_str:
            return None
        
        try:
            # PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
            # Remove D: prefix if present
            if date_str.startswith('D:'):
                date_str = date_str[2:]
            
            # Extract date components
            if len(date_str) >= 14:
                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                hour = int(date_str[8:10])
                minute = int(date_str[10:12])
                second = int(date_str[12:14])
                
                return datetime(year, month, day, hour, minute, second)
            elif len(date_str) >= 8:
                # Date only
                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                
                return datetime(year, month, day)
        
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse PDF date '{date_str}': {e}")
        
        return None
    
    def get_page_text(self, content: bytes, page_number: int) -> str:
        """
        Extract text from a specific page.
        
        Args:
            content: PDF file content as bytes
            page_number: Page number (1-based)
            
        Returns:
            Text content of the specified page
            
        Raises:
            ContentError: If page extraction fails
        """
        try:
            pdf_stream = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            if page_number < 1 or page_number > len(pdf_reader.pages):
                raise ContentError(f"Page {page_number} does not exist. PDF has {len(pdf_reader.pages)} pages.")
            
            page = pdf_reader.pages[page_number - 1]  # Convert to 0-based index
            return page.extract_text()
            
        except PyPDF2.errors.PdfReadError as e:
            raise ContentError(f"Failed to read PDF: {e}")
        except Exception as e:
            raise ContentError(f"Failed to extract page {page_number}: {e}")
    
    def get_page_count(self, content: bytes) -> int:
        """
        Get the number of pages in the PDF.
        
        Args:
            content: PDF file content as bytes
            
        Returns:
            Number of pages in the PDF
            
        Raises:
            ContentError: If PDF reading fails
        """
        try:
            pdf_stream = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            return len(pdf_reader.pages)
            
        except PyPDF2.errors.PdfReadError as e:
            raise ContentError(f"Failed to read PDF: {e}")
        except Exception as e:
            raise ContentError(f"Failed to get page count: {e}")
