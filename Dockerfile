FROM python:3.13-slim

# SDL2 and dependencies needed by pygame (dummy driver still needs them)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsdl2-2.0-0 \
        libsdl2-image-2.0-0 \
        libsdl2-mixer-2.0-0 \
        libsdl2-ttf-2.0-0 \
        libfreetype6 \
        libjpeg62-turbo \
        libpng16-16 \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and tests
COPY piframe/ piframe/
COPY tests/ tests/
COPY config.toml.example .

# Headless by default
ENV SDL_VIDEODRIVER=dummy
ENV SDL_AUDIODRIVER=dummy

CMD ["pytest", "tests/", "-v", "--ignore=tests/test_integration.py"]
