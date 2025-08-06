"""
Enhanced JSON API parsing with support for various standards.

This module provides advanced JSON parsing capabilities including schema validation,
nested data extraction, pagination handling, and support for JSON-LD, HAL, and other API standards.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urljoin, urlparse

from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class JSONParser:
    """Enhanced JSON parser with API standard support."""
    
    def __init__(self):
        """Initialize JSON parser."""
        self.api_standards = {
            'json-ld': self._parse_json_ld,
            'hal': self._parse_hal,
            'json-api': self._parse_json_api,
            'odata': self._parse_odata,
            'collection+json': self._parse_collection_json,
        }
    
    def parse(
        self, 
        content: bytes, 
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Parse JSON content with enhanced API standard detection.
        
        Args:
            content: JSON content as bytes
            url: Optional URL for context
            headers: Optional HTTP headers for additional context
            
        Returns:
            Tuple of (parsed_data, metadata)
            
        Raises:
            ContentError: If JSON parsing fails
        """
        try:
            # Decode and parse JSON
            text_content = content.decode('utf-8', errors='replace')
            data = json.loads(text_content)
            
            # Detect API standard
            api_standard = self._detect_api_standard(data, headers)
            
            # Parse according to detected standard
            if api_standard and api_standard in self.api_standards:
                parsed_data, metadata = self.api_standards[api_standard](data, url)
                metadata['api_standard'] = api_standard
            else:
                parsed_data, metadata = self._parse_generic_json(data, url)
                metadata['api_standard'] = 'generic'
            
            # Add general metadata
            metadata.update({
                'content_type': 'application/json',
                'size_bytes': len(content),
                'size_chars': len(text_content),
                'structure_depth': self._calculate_depth(data),
                'total_keys': self._count_keys(data),
                'has_arrays': self._has_arrays(data),
                'has_nested_objects': self._has_nested_objects(data),
            })
            
            return parsed_data, metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed for {url}: {e}")
            raise ContentError(f"Invalid JSON content: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON from {url}: {e}")
            raise ContentError(f"JSON processing error: {e}")
    
    def _detect_api_standard(self, data: Dict[str, Any], headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Detect which API standard the JSON follows."""
        # Check headers first
        if headers:
            content_type = headers.get('content-type', '').lower()
            if 'application/ld+json' in content_type:
                return 'json-ld'
            elif 'application/hal+json' in content_type:
                return 'hal'
            elif 'application/vnd.api+json' in content_type:
                return 'json-api'
            elif 'application/json;odata' in content_type:
                return 'odata'
            elif 'application/vnd.collection+json' in content_type:
                return 'collection+json'
        
        # Check content structure
        if isinstance(data, dict):
            # JSON-LD detection
            if '@context' in data or '@type' in data or '@id' in data:
                return 'json-ld'
            
            # HAL detection
            if '_links' in data or '_embedded' in data:
                return 'hal'
            
            # JSON API detection
            if 'data' in data and ('type' in data.get('data', {}) or 
                                  (isinstance(data['data'], list) and 
                                   any('type' in item for item in data['data'] if isinstance(item, dict)))):
                return 'json-api'
            
            # OData detection
            if '@odata.context' in data or 'value' in data:
                return 'odata'
            
            # Collection+JSON detection
            if 'collection' in data:
                return 'collection+json'
        
        return None
    
    def _parse_json_ld(self, data: Dict[str, Any], url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse JSON-LD structured data."""
        metadata = {
            'format': 'JSON-LD',
            'context': data.get('@context'),
            'type': data.get('@type'),
            'id': data.get('@id'),
        }
        
        # Extract structured data
        structured_data = {
            'context': data.get('@context'),
            'type': data.get('@type'),
            'id': data.get('@id'),
            'properties': {k: v for k, v in data.items() if not k.startswith('@')},
            'graph': data.get('@graph', []),
        }
        
        # Extract entities if it's a graph
        if '@graph' in data:
            metadata['entity_count'] = len(data['@graph'])
            metadata['entity_types'] = list(set(
                item.get('@type') for item in data['@graph'] 
                if isinstance(item, dict) and '@type' in item
            ))
        
        return structured_data, metadata
    
    def _parse_hal(self, data: Dict[str, Any], url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse HAL (Hypertext Application Language) JSON."""
        metadata = {
            'format': 'HAL',
            'has_links': '_links' in data,
            'has_embedded': '_embedded' in data,
        }
        
        # Extract links
        links = {}
        if '_links' in data:
            for rel, link_data in data['_links'].items():
                if isinstance(link_data, dict):
                    links[rel] = {
                        'href': link_data.get('href'),
                        'templated': link_data.get('templated', False),
                        'type': link_data.get('type'),
                        'title': link_data.get('title'),
                    }
                elif isinstance(link_data, list):
                    links[rel] = [
                        {
                            'href': item.get('href'),
                            'templated': item.get('templated', False),
                            'type': item.get('type'),
                            'title': item.get('title'),
                        }
                        for item in link_data
                    ]
            metadata['link_relations'] = list(links.keys())
        
        # Extract embedded resources
        embedded = {}
        if '_embedded' in data:
            embedded = data['_embedded']
            metadata['embedded_resources'] = list(embedded.keys())
        
        # Extract properties (everything except _links and _embedded)
        properties = {k: v for k, v in data.items() if not k.startswith('_')}
        
        structured_data = {
            'properties': properties,
            'links': links,
            'embedded': embedded,
        }
        
        return structured_data, metadata
    
    def _parse_json_api(self, data: Dict[str, Any], url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse JSON API specification format."""
        metadata = {
            'format': 'JSON API',
            'has_data': 'data' in data,
            'has_included': 'included' in data,
            'has_meta': 'meta' in data,
            'has_links': 'links' in data,
            'has_errors': 'errors' in data,
        }
        
        # Extract main data
        main_data = data.get('data', [])
        if isinstance(main_data, dict):
            main_data = [main_data]
        
        # Extract resource information
        resource_types = set()
        resource_ids = []
        
        for resource in main_data:
            if isinstance(resource, dict):
                if 'type' in resource:
                    resource_types.add(resource['type'])
                if 'id' in resource:
                    resource_ids.append(resource['id'])
        
        metadata.update({
            'resource_count': len(main_data),
            'resource_types': list(resource_types),
            'has_relationships': any(
                'relationships' in resource 
                for resource in main_data 
                if isinstance(resource, dict)
            ),
        })
        
        # Extract included resources
        included = data.get('included', [])
        if included:
            included_types = set(
                resource.get('type') 
                for resource in included 
                if isinstance(resource, dict) and 'type' in resource
            )
            metadata['included_count'] = len(included)
            metadata['included_types'] = list(included_types)
        
        structured_data = {
            'data': main_data,
            'included': included,
            'meta': data.get('meta', {}),
            'links': data.get('links', {}),
            'errors': data.get('errors', []),
        }
        
        return structured_data, metadata
    
    def _parse_odata(self, data: Dict[str, Any], url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse OData JSON format."""
        metadata = {
            'format': 'OData',
            'context': data.get('@odata.context'),
            'has_value': 'value' in data,
            'has_count': '@odata.count' in data,
            'has_next_link': '@odata.nextLink' in data,
        }
        
        # Extract main data
        value = data.get('value', [])
        if not isinstance(value, list):
            value = [value]
        
        metadata['record_count'] = len(value)
        
        # Extract pagination info
        pagination = {}
        if '@odata.count' in data:
            pagination['total_count'] = data['@odata.count']
        if '@odata.nextLink' in data:
            pagination['next_link'] = data['@odata.nextLink']
        if '@odata.deltaLink' in data:
            pagination['delta_link'] = data['@odata.deltaLink']
        
        structured_data = {
            'value': value,
            'context': data.get('@odata.context'),
            'pagination': pagination,
            'metadata': {k: v for k, v in data.items() if k.startswith('@odata.')},
        }
        
        return structured_data, metadata
    
    def _parse_collection_json(self, data: Dict[str, Any], url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse Collection+JSON format."""
        collection = data.get('collection', {})
        
        metadata = {
            'format': 'Collection+JSON',
            'version': collection.get('version'),
            'href': collection.get('href'),
            'has_items': 'items' in collection,
            'has_queries': 'queries' in collection,
            'has_template': 'template' in collection,
        }
        
        items = collection.get('items', [])
        metadata['item_count'] = len(items)
        
        structured_data = {
            'collection': {
                'version': collection.get('version'),
                'href': collection.get('href'),
                'items': items,
                'queries': collection.get('queries', []),
                'template': collection.get('template', {}),
                'error': collection.get('error', {}),
            }
        }
        
        return structured_data, metadata
    
    def _parse_generic_json(self, data: Any, url: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Parse generic JSON data."""
        metadata = {
            'format': 'Generic JSON',
            'root_type': type(data).__name__,
        }
        
        # Handle different root types
        if isinstance(data, dict):
            structured_data = {
                'type': 'object',
                'data': data,
                'keys': list(data.keys()),
            }
            metadata['key_count'] = len(data.keys())
        elif isinstance(data, list):
            structured_data = {
                'type': 'array',
                'data': data,
                'length': len(data),
            }
            metadata['array_length'] = len(data)
            
            # Analyze array contents
            if data:
                item_types = set(type(item).__name__ for item in data[:10])  # Sample first 10
                metadata['item_types'] = list(item_types)
        else:
            structured_data = {
                'type': 'primitive',
                'data': data,
            }
        
        return structured_data, metadata
    
    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum nesting depth of a JSON object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth
    
    def _count_keys(self, obj: Any) -> int:
        """Count total number of keys in nested JSON object."""
        if isinstance(obj, dict):
            return len(obj) + sum(self._count_keys(v) for v in obj.values())
        elif isinstance(obj, list):
            return sum(self._count_keys(item) for item in obj)
        else:
            return 0
    
    def _has_arrays(self, obj: Any) -> bool:
        """Check if JSON contains any arrays."""
        if isinstance(obj, list):
            return True
        elif isinstance(obj, dict):
            return any(self._has_arrays(v) for v in obj.values())
        else:
            return False
    
    def _has_nested_objects(self, obj: Any) -> bool:
        """Check if JSON contains nested objects."""
        if isinstance(obj, dict):
            return any(isinstance(v, dict) or self._has_nested_objects(v) for v in obj.values())
        elif isinstance(obj, list):
            return any(self._has_nested_objects(item) for item in obj)
        else:
            return False
    
    def extract_pagination_info(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract pagination information from various API formats."""
        pagination = {}
        
        # Common pagination patterns
        pagination_fields = {
            'next': ['next', 'next_page', 'nextPage', '@odata.nextLink'],
            'prev': ['prev', 'previous', 'prev_page', 'prevPage'],
            'total': ['total', 'total_count', 'totalCount', '@odata.count'],
            'page': ['page', 'current_page', 'currentPage'],
            'per_page': ['per_page', 'perPage', 'page_size', 'pageSize', 'limit'],
            'offset': ['offset', 'skip'],
        }
        
        for key, possible_fields in pagination_fields.items():
            for field in possible_fields:
                if field in data:
                    pagination[key] = data[field]
                    break
        
        # Check for HAL-style links
        if '_links' in data:
            links = data['_links']
            if 'next' in links:
                pagination['next'] = links['next'].get('href')
            if 'prev' in links:
                pagination['prev'] = links['prev'].get('href')
        
        # Check for JSON API style links
        if 'links' in data:
            links = data['links']
            if 'next' in links:
                pagination['next'] = links['next']
            if 'prev' in links:
                pagination['prev'] = links['prev']
        
        return pagination if pagination else None
