"""
Device integration module for HID Digital Persona 4500 fingerprint reader.
This module handles direct communication with the fingerprint reader hardware.
"""

import os
import sys
import ctypes
import logging
import platform
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any
from ctypes import c_int, c_uint, c_void_p, c_char_p, c_ulong, c_ubyte, POINTER, Structure, c_char, c_ushort

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants for the Digital Persona 4500 device
DP_DEVICE_NAME = "DigitalPersona U.are.U 4500"
DP_VENDOR_ID = 0x05ba  # HID Global vendor ID
DP_PRODUCT_ID = 0x000a  # Digital Persona 4500 product ID

# Define fingerprint quality thresholds
QUALITY_THRESHOLD_HIGH = 80
QUALITY_THRESHOLD_MEDIUM = 60
QUALITY_THRESHOLD_LOW = 40

# Digital Persona SDK Constants
DPFJ_SUCCESS = 0
DPFJ_E_FAILURE = -999
DPFPDD_SUCCESS = 0
DPFPDD_E_FAILURE = -999
DPFPDD_E_DEVICE_FAILURE = -998
DPFPDD_E_DEVICE_BUSY = -997

# Digital Persona SDK Structures
class DPFPDD_DEV_INFO(Structure):
    _fields_ = [
        ("size", c_uint),
        ("name", c_char * 64),
        ("serial_num", c_char * 64),
        ("hw_ver", c_uint),
        ("fw_ver", c_uint),
        ("bcd_rev", c_uint),
    ]

class DPFPDD_DEV_STATUS(Structure):
    _fields_ = [
        ("size", c_uint),
        ("status", c_uint),
        ("finger_detected", c_uint),
    ]

class DPFPDD_CAPTURE_PARAM(Structure):
    _fields_ = [
        ("size", c_uint),
        ("image_fmt", c_uint),
        ("image_proc", c_uint),
        ("image_res", c_uint),
    ]

class DPFPDD_CAPTURE_RESULT(Structure):
    _fields_ = [
        ("size", c_uint),
        ("success", c_uint),
        ("quality", c_int),
        ("score", c_int),
        ("fingerprint_type", c_uint),
    ]

class DeviceStatus(Enum):
    """Enum for device status"""
    DISCONNECTED = 0
    CONNECTED = 1
    BUSY = 2
    ERROR = 3
    READY = 4

class CaptureResult(Enum):
    """Enum for capture result status"""
    SUCCESS = 0
    CANCELED = 1
    TIMEOUT = 2
    DEVICE_BUSY = 3
    DEVICE_ERROR = 4
    QUALITY_TOO_LOW = 5

class FingerprintDevice:
    """Class to handle communication with the HID Digital Persona 4500 fingerprint reader"""
    
    def __init__(self):
        self.device_handle = None
        self.library_handle = None
        self.status = DeviceStatus.DISCONNECTED
        self.device_info = {}
        self._load_driver()
    
    def _load_driver(self) -> bool:
        """
        Load the appropriate driver library based on the operating system.
        Returns True if successful, False otherwise.
        """
        try:
            system = platform.system()
            if system == "Windows":
                # Path to DLLs for Windows
                dll_path = os.path.join(os.path.dirname(__file__), "drivers", "windows", "dpfpdd.dll")
                engine_path = os.path.join(os.path.dirname(__file__), "drivers", "windows", "dpfj.dll")
                
                if not os.path.exists(dll_path) or not os.path.exists(engine_path):
                    # Try to find in system directories if not in local path
                    dll_path = "dpfpdd.dll"
                    engine_path = "dpfj.dll"
                
                self.library_handle = ctypes.WinDLL(dll_path)
                self.engine_handle = ctypes.WinDLL(engine_path)
                
            elif system == "Linux":
                # Path to shared libraries for Linux
                so_path = os.path.join(os.path.dirname(__file__), "drivers", "linux", "libdpfpdd.so")
                engine_path = os.path.join(os.path.dirname(__file__), "drivers", "linux", "libdpfj.so")
                
                if not os.path.exists(so_path) or not os.path.exists(engine_path):
                    # Try to find in system directories if not in local path
                    so_path = "/usr/lib/libdpfpdd.so"
                    engine_path = "/usr/lib/libdpfj.so"
                
                self.library_handle = ctypes.CDLL(so_path)
                self.engine_handle = ctypes.CDLL(engine_path)
                
            elif system == "Darwin":  # macOS
                # Path to dylib for macOS
                dylib_path = os.path.join(os.path.dirname(__file__), "drivers", "macos", "libdpfpdd.dylib")
                engine_path = os.path.join(os.path.dirname(__file__), "drivers", "macos", "libdpfj.dylib")
                
                if not os.path.exists(dylib_path) or not os.path.exists(engine_path):
                    # Try to find in system directories if not in local path
                    dylib_path = "/usr/local/lib/libdpfpdd.dylib"
                    engine_path = "/usr/local/lib/libdpfj.dylib"
                
                self.library_handle = ctypes.CDLL(dylib_path)
                self.engine_handle = ctypes.CDLL(engine_path)
                
            else:
                logger.error(f"Unsupported operating system: {system}")
                return False
            
            # Set function argument and return types
            self._setup_function_prototypes()
            
            logger.info(f"Successfully loaded driver library for {system}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading driver: {str(e)}")
            return False
    
    def _setup_function_prototypes(self):
        """Set up the function prototypes for the Digital Persona SDK"""
        if not self.library_handle:
            return
        
        # Device management functions
        self.library_handle.dpfpdd_init.argtypes = []
        self.library_handle.dpfpdd_init.restype = c_int
        
        self.library_handle.dpfpdd_exit.argtypes = []
        self.library_handle.dpfpdd_exit.restype = c_int
        
        self.library_handle.dpfpdd_query_devices.argtypes = [POINTER(c_uint), POINTER(c_uint)]
        self.library_handle.dpfpdd_query_devices.restype = c_int
        
        self.library_handle.dpfpdd_open.argtypes = [c_uint, POINTER(c_void_p)]
        self.library_handle.dpfpdd_open.restype = c_int
        
        self.library_handle.dpfpdd_close.argtypes = [c_void_p]
        self.library_handle.dpfpdd_close.restype = c_int
        
        self.library_handle.dpfpdd_get_device_info.argtypes = [c_void_p, POINTER(DPFPDD_DEV_INFO)]
        self.library_handle.dpfpdd_get_device_info.restype = c_int
        
        self.library_handle.dpfpdd_get_device_status.argtypes = [c_void_p, POINTER(DPFPDD_DEV_STATUS)]
        self.library_handle.dpfpdd_get_device_status.restype = c_int
        
        # Capture functions
        self.library_handle.dpfpdd_capture.argtypes = [c_void_p, POINTER(DPFPDD_CAPTURE_PARAM), c_uint, POINTER(DPFPDD_CAPTURE_RESULT), POINTER(c_ubyte), POINTER(c_uint)]
        self.library_handle.dpfpdd_capture.restype = c_int
        
        self.library_handle.dpfpdd_cancel.argtypes = [c_void_p]
        self.library_handle.dpfpdd_cancel.restype = c_int
        
        # Feature extraction and template functions
        if self.engine_handle:
            self.engine_handle.dpfj_create_fmd_from_fid.argtypes = [c_uint, c_uint, c_uint, POINTER(c_ubyte), c_uint, c_uint, POINTER(c_ubyte), POINTER(c_uint)]
            self.engine_handle.dpfj_create_fmd_from_fid.restype = c_int
            
            self.engine_handle.dpfj_compare.argtypes = [c_uint, POINTER(c_ubyte), c_uint, c_uint, POINTER(c_ubyte), c_uint, c_uint, POINTER(c_int)]
            self.engine_handle.dpfj_compare.restype = c_int
    
    def connect(self) -> Tuple[bool, str]:
        """
        Connect to the fingerprint reader device.
        Returns a tuple (success, message).
        """
        if not self.library_handle:
            return False, "Driver library not loaded"
        
        try:
            # Initialize the Digital Persona SDK
            result = self.library_handle.dpfpdd_init()
            if result != DPFPDD_SUCCESS:
                return False, f"Failed to initialize Digital Persona SDK. Error code: {result}"
            
            # Query available devices
            device_count = c_uint(0)
            result = self.library_handle.dpfpdd_query_devices(None, ctypes.byref(device_count))
            if result != DPFPDD_SUCCESS:
                return False, f"Failed to query devices. Error code: {result}"
            
            if device_count.value == 0:
                return False, "No fingerprint readers found"
            
            # Open the first available device
            device_handle = c_void_p()
            result = self.library_handle.dpfpdd_open(0, ctypes.byref(device_handle))
            if result != DPFPDD_SUCCESS:
                return False, f"Failed to open device. Error code: {result}"
            
            self.device_handle = device_handle
            
            # Get device information
            dev_info = DPFPDD_DEV_INFO()
            dev_info.size = ctypes.sizeof(DPFPDD_DEV_INFO)
            result = self.library_handle.dpfpdd_get_device_info(self.device_handle, ctypes.byref(dev_info))
            if result != DPFPDD_SUCCESS:
                self.library_handle.dpfpdd_close(self.device_handle)
                self.device_handle = None
                return False, f"Failed to get device information. Error code: {result}"
            
            # Store device information
            self.device_info = {
                "name": dev_info.name.decode('utf-8', errors='ignore'),
                "serial_number": dev_info.serial_num.decode('utf-8', errors='ignore'),
                "hardware_version": dev_info.hw_ver,
                "firmware_version": dev_info.fw_ver,
                "bcd_revision": dev_info.bcd_rev,
                "vendor_id": DP_VENDOR_ID,
                "product_id": DP_PRODUCT_ID,
                "driver_version": "Digital Persona SDK"
            }
            
            self.status = DeviceStatus.CONNECTED
            logger.info(f"Connected to {self.device_info['name']}")
            return True, f"Successfully connected to {self.device_info['name']}"
            
        except Exception as e:
            self.status = DeviceStatus.ERROR
            logger.error(f"Error connecting to device: {str(e)}")
            return False, f"Error connecting to device: {str(e)}"
    
    def disconnect(self) -> bool:
        """
        Disconnect from the fingerprint reader device.
        Returns True if successful, False otherwise.
        """
        if not self.device_handle:
            return True  # Already disconnected
        
        try:
            # Close the device
            result = self.library_handle.dpfpdd_close(self.device_handle)
            if result != DPFPDD_SUCCESS:
                logger.error(f"Error closing device. Error code: {result}")
                return False
            
            # Clean up SDK resources
            self.library_handle.dpfpdd_exit()
            
            self.device_handle = None
            self.status = DeviceStatus.DISCONNECTED
            logger.info("Disconnected from fingerprint reader")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from device: {str(e)}")
            return False
    
    def capture_fingerprint(self, timeout_ms: int = 10000) -> Tuple[CaptureResult, Optional[bytes], int]:
        """
        Capture a fingerprint from the device.
        
        Args:
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Tuple containing:
            - CaptureResult: The result of the capture operation
            - bytes: The captured fingerprint data (or None if capture failed)
            - int: Quality score (0-100, where 100 is best quality)
        """
        if not self.device_handle or self.status != DeviceStatus.CONNECTED:
            logger.error("Device not connected")
            return CaptureResult.DEVICE_ERROR, None, 0
        
        try:
            self.status = DeviceStatus.BUSY
            
            # Set up capture parameters
            capture_params = DPFPDD_CAPTURE_PARAM()
            capture_params.size = ctypes.sizeof(DPFPDD_CAPTURE_PARAM)
            capture_params.image_fmt = 2  # DPFPDD_IMG_FMT_ANSI381
            capture_params.image_proc = 0  # DPFPDD_IMG_PROC_DEFAULT
            capture_params.image_res = 500  # 500 DPI
            
            # Set up capture result
            capture_result = DPFPDD_CAPTURE_RESULT()
            capture_result.size = ctypes.sizeof(DPFPDD_CAPTURE_RESULT)
            
            # Allocate buffer for fingerprint image
            max_image_size = 150000  # Maximum expected image size
            image_buffer = (c_ubyte * max_image_size)()
            image_size = c_uint(max_image_size)
            
            # Capture fingerprint
            result = self.library_handle.dpfpdd_capture(
                self.device_handle,
                ctypes.byref(capture_params),
                timeout_ms,
                ctypes.byref(capture_result),
                image_buffer,
                ctypes.byref(image_size)
            )
            
            if result == DPFPDD_E_DEVICE_BUSY:
                self.status = DeviceStatus.READY
                return CaptureResult.DEVICE_BUSY, None, 0
                
            if result == DPFPDD_E_DEVICE_FAILURE:
                self.status = DeviceStatus.ERROR
                return CaptureResult.DEVICE_ERROR, None, 0
                
            if result != DPFPDD_SUCCESS:
                self.status = DeviceStatus.ERROR
                logger.error(f"Error capturing fingerprint. Error code: {result}")
                return CaptureResult.DEVICE_ERROR, None, 0
            
            # Check capture quality
            quality_score = capture_result.quality
            if quality_score < QUALITY_THRESHOLD_LOW:
                self.status = DeviceStatus.READY
                return CaptureResult.QUALITY_TOO_LOW, None, quality_score
            
            # Extract fingerprint data
            fingerprint_data = bytes(image_buffer[:image_size.value])
            
            # Create feature template from fingerprint image
            if self.engine_handle:
                # Allocate buffer for feature template
                max_template_size = 2000  # Maximum expected template size
                template_buffer = (c_ubyte * max_template_size)()
                template_size = c_uint(max_template_size)
                
                # Create feature template
                result = self.engine_handle.dpfj_create_fmd_from_fid(
                    0,  # DPFJ_FID_FORMAT_ANSI381
                    0,  # DPFJ_FMD_FORMAT_ANSI378
                    0,  # DPFJ_FMD_ISO_NORMAL
                    image_buffer,
                    image_size.value,
                    0,  # DPFJ_FMD_PURPOSE_VERIFY
                    template_buffer,
                    ctypes.byref(template_size)
                )
                
                if result == DPFJ_SUCCESS:
                    # Use the template instead of the raw image
                    fingerprint_data = bytes(template_buffer[:template_size.value])
            
            self.status = DeviceStatus.READY
            logger.info(f"Fingerprint captured successfully with quality score: {quality_score}")
            return CaptureResult.SUCCESS, fingerprint_data, quality_score
            
        except Exception as e:
            self.status = DeviceStatus.ERROR
            logger.error(f"Error capturing fingerprint: {str(e)}")
            return CaptureResult.DEVICE_ERROR, None, 0
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the device.
        Returns a dictionary with status information.
        """
        status_info = {
            "status": self.status.name,
            "connected": self.status == DeviceStatus.CONNECTED or self.status == DeviceStatus.READY,
            "device_info": self.device_info if self.device_handle else {}
        }
        
        # If connected, get real-time device status
        if self.device_handle and (self.status == DeviceStatus.CONNECTED or self.status == DeviceStatus.READY):
            try:
                dev_status = DPFPDD_DEV_STATUS()
                dev_status.size = ctypes.sizeof(DPFPDD_DEV_STATUS)
                result = self.library_handle.dpfpdd_get_device_status(self.device_handle, ctypes.byref(dev_status))
                
                if result == DPFPDD_SUCCESS:
                    status_info["finger_detected"] = bool(dev_status.finger_detected)
                    status_info["device_status_code"] = dev_status.status
            except Exception as e:
                logger.error(f"Error getting device status: {str(e)}")
        
        return status_info
    
    def is_connected(self) -> bool:
        """Check if the device is connected"""
        return self.status == DeviceStatus.CONNECTED or self.status == DeviceStatus.READY
    
    def compare_templates(self, template1: bytes, template2: bytes) -> Tuple[bool, int]:
        """
        Compare two fingerprint templates and return a match score.
        
        Args:
            template1: First template
            template2: Second template
            
        Returns:
            Tuple containing:
            - bool: True if templates match, False otherwise
            - int: Match score (0-100, where 100 is a perfect match)
        """
        if not self.engine_handle:
            return False, 0
        
        try:
            # Convert templates to ctypes arrays
            template1_array = (c_ubyte * len(template1)).from_buffer_copy(template1)
            template2_array = (c_ubyte * len(template2)).from_buffer_copy(template2)
            
            # Compare templates
            score = c_int(0)
            result = self.engine_handle.dpfj_compare(
                0,  # DPFJ_FMD_FORMAT_ANSI378
                template1_array,
                len(template1),
                0,  # DPFJ_FMD_FORMAT_ANSI378
                template2_array,
                len(template2),
                0,  # DPFJ_FMD_PURPOSE_VERIFY
                ctypes.byref(score)
            )
            
            if result != DPFJ_SUCCESS:
                logger.error(f"Error comparing templates. Error code: {result}")
                return False, 0
            
            # Convert score to percentage (0-100)
            match_score = min(100, max(0, score.value))
            
            # Determine if it's a match (threshold is typically around 40-60)
            is_match = match_score >= 50
            
            return is_match, match_score
            
        except Exception as e:
            logger.error(f"Error comparing templates: {str(e)}")
            return False, 0

# Create a singleton instance of the fingerprint device
device = FingerprintDevice()

def get_device() -> FingerprintDevice:
    """Get the singleton instance of the fingerprint device"""
    return device

