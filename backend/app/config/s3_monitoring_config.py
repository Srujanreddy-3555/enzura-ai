"""
S3 Monitoring Configuration
Configuration settings for the S3 monitoring service.
"""

import os
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

class S3MonitoringConfig:
    """Configuration for S3 monitoring service."""
    
    # Processing settings
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv("S3_MAX_CONCURRENT_DOWNLOADS", "5"))
    MAX_FILE_SIZE_MB = int(os.getenv("S3_MAX_FILE_SIZE_MB", "500"))
    TEMP_DIR = Path(os.getenv("S3_TEMP_DIR", "/tmp/enzura_processing"))
    
    # Retry settings
    MAX_RETRIES = int(os.getenv("S3_MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS = int(os.getenv("S3_RETRY_DELAY_SECONDS", "60"))
    
    # Queue settings
    MAX_QUEUE_SIZE = int(os.getenv("S3_MAX_QUEUE_SIZE", "100"))
    PROCESSING_TIMEOUT_SECONDS = int(os.getenv("S3_PROCESSING_TIMEOUT_SECONDS", "3600"))
    
    # Supported audio formats
    SUPPORTED_AUDIO_FORMATS = {
        '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.mp4'
    }
    
    # Sales rep detection patterns
    SALES_REP_PATTERNS = [
        r'/([^/]+)/',  # Folder name
        r'([^/]+)_',   # Prefix before underscore
        r'_([^/]+)\.', # Suffix before extension
        r'([^/]+)-',   # Prefix before dash
        r'-([^/]+)\.', # Suffix before extension
    ]
    
    # Default processing schedules
    DEFAULT_SCHEDULES = {
        "hourly": 3600,
        "daily": 86400,
        "twice_daily": 43200,
        "every_6_hours": 21600,
        "every_2_hours": 7200,
    }
    
    @classmethod
    def get_schedule_interval(cls, schedule: str) -> int:
        """Get scan interval in seconds for a given schedule."""
        return cls.DEFAULT_SCHEDULES.get(schedule, 86400)  # Default to daily
    
    @classmethod
    def is_supported_audio_format(cls, filename: str) -> bool:
        """Check if file format is supported."""
        extension = Path(filename).suffix.lower()
        return extension in cls.SUPPORTED_AUDIO_FORMATS
    
    @classmethod
    def get_temp_file_path(cls, original_filename: str) -> Path:
        """Get temporary file path for processing."""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(datetime.utcnow().timestamp())
        return cls.TEMP_DIR / f"{timestamp}_{original_filename}"

# Global configuration instance
config = S3MonitoringConfig()
