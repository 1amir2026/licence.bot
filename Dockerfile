FROM node:18-bullseye

# ---------------- system deps ----------------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python-is-python3 \
    blender \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------- workdir ----------------
WORKDIR /app

# ---------------- copy project ----------------
COPY . .

# ---------------- python deps ----------------
RUN pip3 install --no-cache-dir -r requirements.txt

# ---------------- node deps ----------------
RUN cd processor && npm install

# ---------------- env ----------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ---------------- IMPORTANT ----------------
# اگر Railway / Render داری، پورت ممکنه لازم نباشه
ENV PORT=3000

# ---------------- start python bot ----------------
CMD ["python3", "bot/bot.py"]
