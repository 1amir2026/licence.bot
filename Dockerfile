FROM node:18-bullseye

# ---------------- deps ----------------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python-is-python3 \
    blender \
    ffmpeg \
    git \
    curl \
    openjdk-17-jre \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------- copy project ----------------
COPY . .

# ---------------- AUTO FIX MCprep FOLDER ----------------
RUN if [ -d "MCprep_addon" ]; then mv MCprep_addon mcprep; fi && \
    if [ -d "MCPrep_addon" ]; then mv MCPrep_addon mcprep; fi && \
    if [ -d "MCPREP_addon" ]; then mv MCPREP_addon mcprep; fi

# ---------------- python deps ----------------
RUN pip3 install --no-cache-dir -r requirements.txt

# ---------------- node deps ----------------
RUN cd processor && npm install

# ---------------- install mcprep into blender path ----------------
RUN mkdir -p /usr/share/blender/scripts/addons && \
    cp -r mcprep /usr/share/blender/scripts/addons/mcprep || true

# Download latest jmc2obj.jar
RUN curl -L -o /app/processor/jmc2obj.jar https://github.com/jmc2obj/j-mc-2-obj/releases/latest/download/jmc2obj.jar || echo "Warning: jmc2obj download failed"

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python3", "bot/bot.py"]
