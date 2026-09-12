FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --break-system-packages .

EXPOSE 6053/udp 6053/tcp

VOLUME ["/app/data"]

ENTRYPOINT ["jablo2esphome"]
CMD ["/app/config.yaml"]