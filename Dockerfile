# Dockerfile

FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# 显式暴露端口5000
EXPOSE 5000

CMD ["python", "app.py"]
