# Testing Guide for OFFSET_INVALID Fix

## Manual Testing Steps

### Prerequisites
1. Start the bot and web server: `python3 main.py`
2. Upload a file to the bot (preferably 1.5MB or larger)
3. Get the streaming link from the bot's response

### Test Cases

#### Test 1: Full File Stream (No Range Header)
```bash
curl -i http://localhost:7860/stream/{chat_id}/{message_id}
```
**Expected**: Status 206, entire file downloads

#### Test 2: Range Request from Start
```bash
curl -i -H "Range: bytes=0-1000000" http://localhost:7860/stream/{chat_id}/{message_id}
```
**Expected**: Status 206, Content-Range: bytes 0-1000000/[file_size]

#### Test 3: Range Request from Middle (Within First Chunk)
```bash
curl -i -H "Range: bytes=500000-1000000" http://localhost:7860/stream/{chat_id}/{message_id}
```
**Expected**: Status 206, Content-Range: bytes 500000-1000000/[file_size], correct data

#### Test 4: Range Request Crossing Chunk Boundary
```bash
curl -i -H "Range: bytes=1000000-2000000" http://localhost:7860/stream/{chat_id}/{message_id}
```
**Expected**: Status 206, spanning chunks 0 and 1, correct data

#### Test 5: Range Request Starting at Chunk Boundary
```bash
curl -i -H "Range: bytes=1048576-2097151" http://localhost:7860/stream/{chat_id}/{message_id}
```
**Expected**: Status 206, exactly chunk 1, correct data

#### Test 6: VLC/Browser Streaming
1. Open VLC: Media > Open Network Stream
2. Enter: `http://localhost:7860/stream/{chat_id}/{message_id}`
3. Try seeking to different positions

**Expected**: 
- Video plays smoothly
- Seeking works without errors
- No OFFSET_INVALID errors in logs

#### Test 7: Browser Range Requests
Open in browser: `http://localhost:7860/stream/{chat_id}/{message_id}`

**Expected**:
- File starts downloading/playing
- Browser can seek (for video/audio files)
- No errors in console or server logs

## Automated Test

Run the offset calculation validation:
```bash
python3 test_offset_calculation.py
```

**Expected**: All tests pass ✓

## Expected Logs

### Before Fix (with error):
```
ERROR - pyrogram.errors.exceptions.bad_request_400.OffsetInvalid: Telegram says: [400 OFFSET_INVALID]
```

### After Fix (success):
```
INFO - Stream request for chat_id={id}, message_id={id}
INFO - Range: bytes {start}-{end}/{total}
INFO - Streaming with chunk_offset={chunk}, skip_bytes={bytes}
```

## Known Good Values (for 1.5MB file)

| Byte Range | Chunk Offset | Skip Bytes | Expected Behavior |
|------------|--------------|------------|-------------------|
| 0-1500000 | 0 | 0 | Full file |
| 500000-1000000 | 0 | 500000 | Mid first chunk |
| 1048576-1500000 | 1 | 0 | Start of second chunk |
| 1400000-1500000 | 1 | 351424 | Mid second chunk |

## Troubleshooting

### Still Getting OFFSET_INVALID
- Check that `CHUNK_SIZE = 1024 * 1024` is correct
- Verify offset conversion: `chunk_offset = start // CHUNK_SIZE`
- Ensure `stream_media(offset=chunk_offset)` not `offset=start`

### Incorrect Data Returned
- Verify `bytes_to_skip` is applied to first chunk only
- Check that final chunk is trimmed to `bytes_left`
- Ensure `first_chunk` flag is properly reset

### Connection Drops
- Check network/proxy stability
- Verify self-healing logic recalculates offsets correctly
- Check Telegram API rate limits
