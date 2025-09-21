"""
Utility functions
"""

import re
import hashlib
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

def validate_urls(urls: List[str]) -> List[str]:
    """Validate and filter tweet URLs"""
    valid_urls = []
    tweet_pattern = r'https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+'
    
    for url in urls:
        url = url.strip()
        if re.match(tweet_pattern, url):
            valid_urls.append(url)
    
    return valid_urls

def extract_tweet_id(url: str) -> str:
    """Extract tweet ID from URL"""
    match = re.search(r'/status/(\d+)', url)
    return match.group(1) if match else hashlib.md5(url.encode()).hexdigest()[:8]

def generate_filename(tweet_id: str, format: str, include_metadata: bool = False) -> str:
    """Generate filename for screenshot"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if include_metadata:
        return f"tweet_{tweet_id}_{timestamp}.{format}"
    else:
        return f"tweet_{tweet_id}.{format}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    return re.sub(r'[^\w\-_\.]', '_', filename)

def clean_tweet_content(content: str) -> str:
    """Clean tweet content for filename generation"""
    # Remove URLs, mentions, hashtags for cleaner filenames
    cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', content)
    cleaned = re.sub(r'@\w+', '', cleaned)
    cleaned = re.sub(r'#\w+', '', cleaned)
    return cleaned.strip()[:50]  # Limit length
