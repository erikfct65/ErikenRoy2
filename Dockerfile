# Gebruik een officiële Python-image als basis
FROM python:3.11-slim

# Zet de werkmap in de container
WORKDIR /app

# Installeer de benodigde systeem-libraries voor Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # --- Benodigdheden voor Chrome ---
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # --- Cleanup ---
    && rm -rf /var/lib/apt/lists/*

# Download en installeer Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb

# Kopieer de requirements en installeer de Python-bibliotheken
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de rest van de applicatiecode
COPY . .

# Definieer het commando dat moet worden uitgevoerd als de container start
CMD ["python", "discounter_bot.py"]
