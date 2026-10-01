FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --uid 10001 --create-home battery \
    && mkdir -p /app/var \
    && chown -R battery:battery /app

COPY --chown=battery:battery app.py /app/app.py
COPY --chown=battery:battery battery /app/battery
COPY --chown=battery:battery scripts /app/scripts
COPY --chown=battery:battery static /app/static

USER battery
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

FROM runtime AS test
COPY --chown=battery:battery tests /app/tests
COPY --chown=battery:battery conftest.py /app/conftest.py
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
