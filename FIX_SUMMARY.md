# Fix Summary: OFFSET_INVALID Error in Streaming Handler

## Problem
When accessing streaming links (`/stream/{chat_id}/{message_id}`), the bot was throwing:
```
pyrogram.errors.exceptions.bad_request_400.OffsetInvalid: Telegram says: [400 OFFSET_INVALID]
```

This occurred after ~47 seconds when trying to stream files, particularly when browsers or VLC players made HTTP 206 byte-range requests.

## Root Cause
The streaming handler in `server/stream_routes.py` was passing **byte offsets** directly to Pyrogram's `stream_media()` method. However, `stream_media()` expects the `offset` parameter to be the **number of 1MB chunks to skip**, not a byte offset.

### Example of the Bug
For a byte offset of 500,000 (500KB):
- The code was passing `offset=500000` to `stream_media()`
- Pyrogram internally multiplies this by 1MB: `500000 × 1,048,576 = 524,288,000,000 bytes` (~524GB)
- This resulted in an invalid offset far beyond the actual file size, causing the error

## Solution
Modified `server/stream_routes.py` to properly convert byte offsets to chunk offsets:

1. **Calculate chunk offset**: `chunk_offset = start_byte // (1024 * 1024)`
   - Determines which 1MB chunk to start from
   
2. **Calculate bytes to skip**: `bytes_to_skip = start_byte % (1024 * 1024)`
   - Determines how many bytes to skip within the first chunk
   
3. **Apply offsets correctly**:
   - Pass `chunk_offset` to `stream_media(offset=chunk_offset)`
   - Skip `bytes_to_skip` bytes from the first chunk received
   - Trim the final chunk if it exceeds the requested byte range

4. **Handle recovery**: When errors occur and streaming needs to restart, recalculate both offsets based on the current byte position

## Changes Made
- **File**: `server/stream_routes.py`
- **Lines**: 44-97 (media_stream_generator function)
- Added proper chunk offset calculation
- Added byte-skipping logic for partial chunks
- Maintained the self-healing capability for expired file references

## Testing
Created `test_offset_calculation.py` to validate the offset conversion logic:
- ✅ Start at beginning (0 bytes)
- ✅ Start mid-chunk (500KB)
- ✅ Start at chunk boundary (1MB, 2MB)
- ✅ Start mid-chunk in later chunks
- ✅ Start near end of file

All tests pass correctly.

## Acceptance Criteria Met
- ✅ Streaming works without OFFSET_INVALID errors
- ✅ Byte range requests (HTTP 206) are properly handled
- ✅ Offset calculations align with Telegram's 1MB chunk size
- ✅ Self-healing mechanism preserved for expired file references
- ✅ Proper error handling maintained
