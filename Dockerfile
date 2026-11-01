# Reproducible gilvy renders. ffmpeg is the system dependency; Python deps are pinned.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/gilvy
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY skills ./skills
COPY docs ./docs
COPY AGENTS.md ./AGENTS.md

RUN pip install --no-cache-dir .

WORKDIR /work
ENTRYPOINT ["gilvy"]
CMD ["--help"]
