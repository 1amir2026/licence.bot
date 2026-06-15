FROM node:18-bullseye as node_builder

WORKDIR /app/processor
COPY processor/ .
RUN npm install


FROM python:3.11

RUN apt-get update && apt-get install -y \
    blender \
    ffmpeg \
    git \
    curl \
    openjdk-17-jre \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# copy node modules from first stage
COPY --from=node_builder /app/processor /app/processor

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pillow

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "bot/bot.py"]
