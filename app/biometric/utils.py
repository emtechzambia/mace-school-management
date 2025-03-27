"""
Utility functions for fingerprint processing and template management.
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_features(fingerprint_data: bytes) -> Optional[bytes]:
    """
    Extract features from raw fingerprint data.
    
    Args:
        fingerprint_data: Raw fingerprint image data
        
    Returns:
        Extracted feature data or None if extraction failed
    """
    # The feature extraction is now handled directly in the device.py module
    # using the Digital Persona SDK's dpfj_create_fmd_from_fid function
    # This function is kept for compatibility
    return fingerprint_data

def create_template(feature_data: List[bytes]) -> Optional[bytes]:
    """
    Create a fingerprint template from multiple feature sets.
    
    Args:
        feature_data: List of feature data from multiple captures
        
    Returns:
        Template data or None if creation failed
    """
    if not feature_data or len(feature_data) < 2:
        logger.error("At least 2 feature sets are required to create a template")
        return None
    
    try:
        # In a real implementation with the Digital Persona SDK, you would use
        # the SDK's template consolidation function. For now, we'll use the
        # highest quality template (assumed to be the last one)
        return feature_data[-1]
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        return None

def compare_templates(template1: bytes, template2: bytes) -> Tuple[bool, float]:
    """
    Compare two fingerprint templates and return a match score.
    
    Args:
        template1: First template
        template2: Second template
        
    Returns:
        Tuple containing:
        - bool: True if templates match, False otherwise
        - float: Match score (0-100, where 100 is a perfect match)
    """
    # This function is now a wrapper around the device's compare_templates method
    # which uses the Digital Persona SDK's dpfj_compare function
    from app.biometric.device import get_device
    device = get_device()
    return device.compare_templates(template1, template2)

def encode_template(template_data: bytes) -> str:
    """
    Encode template data to a string for storage.
    
    Args:
        template_data: Template data bytes
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(template_data).decode('utf-8')

def decode_template(encoded_template: str) -> Optional[bytes]:
    """
    Decode a stored template string back to bytes.
    
    Args:
        encoded_template: Base64 encoded template string
        
    Returns:
        Template data bytes or None if decoding failed
    """
    try:
        return base64.b64decode(encoded_template)
    except Exception as e:
        logger.error(f"Error decoding template: {str(e)}")
        return None

def get_template_info(template_data: bytes) -> Dict[str, Any]:
    """
    Get information about a template.
    
    Args:
        template_data: Template data bytes
        
    Returns:
        Dictionary with template information
    """
    template_hash = hashlib.sha256(template_data).hexdigest()
    return {
        "size": len(template_data),
        "hash": template_hash[:16],  # First 16 chars of hash for display
        "created": datetime.now().isoformat()
    }

