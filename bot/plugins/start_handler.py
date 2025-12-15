from pyrogram import Client, filters
from config import Config

@Client.on_message(filters.private)
async def handle_stream(client, message):
    # Debug flush
    print(f"✅ MESSAGE HIT: {message.chat.id}", flush=True)

    if message.text:
         await message.reply_text("👋 **Working!** Send me a file.")
         return
         
    # Handle File
    file = message.document or message.video or message.audio
    
    if file:
        file_name = getattr(file, "file_name", "Unknown")
        stream_link = f"{Config.URL}/stream/{message.chat.id}/{message.id}"
        
        await message.reply_text(
            f"**🎥 Stream Ready**\n"
            f"📁 `{file_name}`\n"
            f"🔗 [Stream Link]({stream_link})"
        )