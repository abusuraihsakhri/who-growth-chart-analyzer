FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies from pyproject.toml
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

# Security: refuse to run without AUDIT_SECRET_KEY
RUN echo '#!/bin/bash\nif [ -z "$AUDIT_SECRET_KEY" ]; then echo "ERROR: AUDIT_SECRET_KEY must be set" >&2; exit 1; fi\nexec "$@"' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "cli.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
