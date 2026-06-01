FROM node:18-bullseye

# نصب Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip python-is-python3 && \
    apt-get clean

WORKDIR /app

# کپی کل پروژه
COPY . .

# نصب پکیج‌های Python
RUN pip install --no-cache-dir -r requirements.txt

# نصب پکیج‌های Node.js
RUN cd processor && npm install

# پورت Railway
ENV PORT=3000

# اجرای برنامه Node.js
CMD ["node", "index.js"]
