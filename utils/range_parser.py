"""
HTTP Range Header Parser for Video Streaming.

Handles byte-range requests (HTTP 206 Partial Content) to support:
- Video seeking/scrubbing in players
- Resuming interrupted downloads
- Efficient bandwidth usage
"""


def parse_range(range_header: str, file_size: int):
    """
    Parse HTTP Range header and return byte offsets.
    
    Supports standard Range header formats:
    - "bytes=0-1023" - Request specific range
    - "bytes=1024-" - Request from offset to end
    - "bytes=-1024" - Request last N bytes (not supported)
    
    Args:
        range_header (str): HTTP Range header value (e.g., "bytes=0-1023")
        file_size (int): Total file size in bytes
        
    Returns:
        tuple: (start, end) byte offsets if valid, None if invalid
        
    Example:
        >>> parse_range("bytes=0-1023", 10000)
        (0, 1023)
        
        >>> parse_range("bytes=5000-", 10000)
        (5000, 9999)
        
        >>> parse_range("invalid", 10000)
        None
    """
    try:
        # Validate header format
        if not range_header or "=" not in range_header:
            return None
        
        # Split into unit and range values
        unit, ranges = range_header.split("=")
        if unit != "bytes":
            return None
        
        # Parse start and end positions
        start_str, end_str = ranges.split("-")
        
        start = int(start_str)
        # If end is missing, serve from start to file end
        end = int(end_str) if end_str else file_size - 1
        
        # Validate range boundaries
        if start >= file_size:
            return None
        if end >= file_size:
            end = file_size - 1
            
        return start, end
    except ValueError:
        # Invalid format or non-numeric values
        return None