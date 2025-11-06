import os
from typing import List, Tuple, Optional
import logging
import shutil

# Try to import pydub, but make it optional
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
    
    # Try to set ffmpeg path explicitly if available
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        # Set ffmpeg path for pydub
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path
        logger = logging.getLogger(__name__)
        logger.info(f"✅ pydub configured with ffmpeg at: {ffmpeg_path}")
    else:
        logger = logging.getLogger(__name__)
        logger.warning("⚠️ ffmpeg not found in PATH, pydub may not work correctly")
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ pydub not available, duration extraction will not work")

# Supported audio formats
SUPPORTED_AUDIO_FORMATS = {
    'audio/mpeg': '.mp3',
    'audio/wav': '.wav', 
    'audio/mp4': '.m4a',
    'audio/aac': '.aac',
    'audio/ogg': '.ogg',
    'audio/flac': '.flac'
}

# Maximum file size (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

class FileValidator:
    """Utility class for validating uploaded files"""
    
    @staticmethod
    def validate_file_size(file_size: int) -> Tuple[bool, Optional[str]]:
        """Validate file size"""
        if file_size > MAX_FILE_SIZE:
            return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds maximum allowed size (100MB)"
        return True, None
    
    @staticmethod
    def validate_file_type(file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate file type using extension and basic magic number check"""
        try:
            # Check file extension
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension not in [ext for ext in SUPPORTED_AUDIO_FORMATS.values()]:
                return False, f"Unsupported file extension: {file_extension}"
            
            # Basic magic number validation for common audio formats
            if len(file_content) < 4:
                return False, "File too small to be a valid audio file"
            
            # Check for common audio file signatures
            if file_extension == '.mp3':
                # MP3 files start with ID3 tag or MP3 frame sync
                if not (file_content.startswith(b'ID3') or file_content.startswith(b'\xff\xfb')):
                    logger.warning(f"MP3 file may not have valid header: {filename}")
            elif file_extension == '.wav':
                # WAV files start with RIFF header
                if not file_content.startswith(b'RIFF'):
                    logger.warning(f"WAV file may not have valid header: {filename}")
            elif file_extension == '.m4a':
                # M4A files start with ftyp box
                if not (file_content.startswith(b'ftyp') or file_content[4:8] == b'ftyp'):
                    logger.warning(f"M4A file may not have valid header: {filename}")
            
            # For now, we'll be lenient and just check the extension
            # In production, you might want stricter validation
            return True, None
            
        except Exception as e:
            return False, f"Error validating file type: {str(e)}"
    
    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, Optional[str]]:
        """Validate filename"""
        if not filename or len(filename.strip()) == 0:
            return False, "Filename cannot be empty"
        
        if len(filename) > 255:
            return False, "Filename too long (max 255 characters)"
        
        # Check for dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in filename:
                return False, f"Filename contains invalid character: {char}"
        
        return True, None

class AudioProcessor:
    """Utility class for processing audio files"""
    
    @staticmethod
    def get_audio_duration(file_path: str) -> Optional[int]:
        """Get audio duration in seconds using pydub (which uses ffmpeg)"""
        if not PYDUB_AVAILABLE:
            logger.warning("❌ pydub not available, cannot get audio duration")
            return None
        
        try:
            logger.info(f"🔍 Loading audio file with pydub: {file_path}")
            # Use pydub to load the audio file
            # pydub internally uses ffmpeg to decode the audio
            audio = AudioSegment.from_file(file_path)
            
            # Get duration in milliseconds and convert to seconds
            duration_ms = len(audio)
            duration_seconds = duration_ms // 1000
            
            logger.info(f"✅ Audio loaded successfully: {duration_ms}ms = {duration_seconds} seconds")
            return duration_seconds
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"❌ Error getting audio duration from {file_path}: {e}")
            
            # Check if it's an ffmpeg-related error
            if "ffmpeg" in error_msg or "converter" in error_msg:
                logger.error(f"❌ FFMPEG ERROR: This indicates ffmpeg is not properly configured")
                logger.error(f"   Try installing ffmpeg and adding it to your system PATH")
                # Try to find ffmpeg manually
                try:
                    import shutil
                    ffmpeg_path = shutil.which('ffmpeg')
                    if ffmpeg_path:
                        logger.info(f"   ffmpeg found at: {ffmpeg_path}")
                        logger.info(f"   Attempting to set ffmpeg path explicitly...")
                        AudioSegment.converter = ffmpeg_path
                        AudioSegment.ffmpeg = ffmpeg_path
                        # Try again with explicit path
                        try:
                            audio = AudioSegment.from_file(file_path)
                            duration_ms = len(audio)
                            duration_seconds = duration_ms // 1000
                            logger.info(f"✅ Retry with explicit ffmpeg path succeeded: {duration_seconds}s")
                            return duration_seconds
                        except Exception as retry_error:
                            logger.error(f"❌ Retry with explicit path also failed: {retry_error}")
                    else:
                        logger.error(f"   ❌ ffmpeg NOT found in system PATH")
                except Exception as path_error:
                    logger.error(f"   Error checking ffmpeg path: {path_error}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def get_audio_info(file_path: str) -> dict:
        """Get comprehensive audio file information"""
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available, cannot get audio info")
            return {}
        try:
            audio = AudioSegment.from_file(file_path)
            return {
                'duration_seconds': len(audio) // 1000,
                'sample_rate': audio.frame_rate,
                'channels': audio.channels,
                'bit_depth': audio.sample_width * 8,
                'format': os.path.splitext(file_path)[1].lower()
            }
        except Exception as e:
            logger.error(f"Error getting audio info: {e}")
            return {}
    
    @staticmethod
    def convert_to_mp3(file_path: str, output_path: str) -> bool:
        """Convert audio file to MP3 format"""
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available, cannot convert audio")
            return False
        try:
            audio = AudioSegment.from_file(file_path)
            audio.export(output_path, format="mp3")
            return True
        except Exception as e:
            logger.error(f"Error converting to MP3: {e}")
            return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace dangerous characters
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "unnamed_file"
    
    return sanitized

def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return os.path.splitext(filename)[1].lower()

def is_audio_file(filename: str) -> bool:
    """Check if file is an audio file based on extension"""
    extension = get_file_extension(filename)
    return extension in [ext for ext in SUPPORTED_AUDIO_FORMATS.values()]
