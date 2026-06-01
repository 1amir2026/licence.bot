FROM node:18-bullseye

RUN apt-get update && apt-get install -y python3 python3-pip python3-venv

WORKDIR /app
COPY . .

RUN pip3 install -r requirements.txt
RUN cd processor && npm install

CMD ["python3", "bot/bot.py"]
