FROM python:3.11-slim

WORKDIR /app

RUN pip3 install --no-cache-dir flask groq pypdf

COPY . /app

EXPOSE 5000

CMD ["python3", "app.py"]