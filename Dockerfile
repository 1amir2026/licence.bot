FROM node:18-bullseye AS node_builder

WORKDIR /app/processor

COPY processor/ .

RUN npm install


FROM python:3.11

# ---------------- deps ----------------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python-is-python3 \
    blender \
    ffmpeg \
    git \
    curl \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------- copy project ----------------
COPY . .

# ---------------- AUTO FIX MCprep FOLDER ----------------
RUN if [ -d "MCprep_addon" ]; then mv MCprep_addon mcprep; fi && \
    if [ -d "MCPrep_addon" ]; then mv MCPrep_addon mcprep; fi && \
    if [ -d "MCPREP_addon" ]; then mv MCPREP_addon mcprep; fi

# ---------------- copy node build ----------------
COPY --from=node_builder /app/processor /app/processor

# ---------------- python deps ----------------
RUN pip3 install --no-cache-dir -r requirements.txt

# ---------------- pillow ----------------
RUN pip3 install --no-cache-dir pillow

# ---------------- blender addons ----------------
RUN mkdir -p /usr/share/blender/scripts/addons && \
    cp -r mcprep /usr/share/blender/scripts/addons/mcprep || true

# ---------------- jmc2obj ----------------
RUN curl -L -o /app/processor/jmc2obj.jar https://github.com/jmc2obj/j-mc-2-obj/releases/latest/download/jmc2obj.jar || true

# ---------------- env ----------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ---------------- run ----------------
CMD ["python", "bot/bot.py"]
