# In your backend/app/models.py - CREATE THIS FILE

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ScreenshotOptions(BaseModel):
    width: int = 600
    format: str = "png"  # png or jpg
    theme: str = "light"  # light or dark
    background: str = "white"
    border_radius: int = 12
    include_metadata: bool = True

class BulkScreenshotRequest(BaseModel):
    urls: List[str]
    options: Optional[ScreenshotOptions] = None

class ScreenshotResult(BaseModel):
    url: str
    success: bool
    image_base64: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None
    dimensions: Optional[Dict[str, int]] = None
    error: Optional[str] = None