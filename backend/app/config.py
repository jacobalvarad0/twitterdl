"""
Application configuration
"""

import os
from typing import List

class Settings:
    """Application settings"""
    
    def __init__(self):
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        
        # Security settings - parse comma-separated values
        allowed_hosts_str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
        self.ALLOWED_HOSTS: List[str] = [host.strip() for host in allowed_hosts_str.split(",")]
        
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")  
        self.CORS_ORIGINS: List[str] = [origin.strip() for origin in cors_origins_str.split(",")]
        
        # Screenshot settings
        self.MAX_CONCURRENT_SCREENSHOTS: int = int(os.getenv("MAX_CONCURRENT_SCREENSHOTS", "3"))
        self.SCREENSHOT_TIMEOUT: int = int(os.getenv("SCREENSHOT_TIMEOUT", "30"))
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
        
        # Storage settings
        self.TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/screenshots")
        self.MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
        
        # Rate limiting
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

settings = Settings()
