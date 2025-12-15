FROM python:3.10-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*

# Setup directory
WORKDIR /app

# Copy Requirements and Install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Application Code
COPY . .

# CRITICAL PERMISSION FIX:
# Change ownership of the folder to user 1000 BEFORE switching users.
# This allows the bot to write 'session.session' without "Permission Denied" errors.
RUN chown -R 1000:1000 /app

# Switch to standard HF User
USER 1000

CMD ["python", "main.py"]