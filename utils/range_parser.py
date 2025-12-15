# Handles HTTP Byte Ranges for seeking in video
def parse_range(range_header: str, file_size: int):
    try:
        if not range_header or "=" not in range_header:
            return None
        
        unit, ranges = range_header.split("=")
        if unit != "bytes":
            return None
            
        start_str, end_str = ranges.split("-")
        
        start = int(start_str)
        # If end is missing, take up to file size
        end = int(end_str) if end_str else file_size - 1
        
        if start >= file_size:
            return None
        if end >= file_size:
            end = file_size - 1
            
        return start, end
    except ValueError:
        return None