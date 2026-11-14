FROM python:3.12-slim AS web-build
WORKDIR /source
COPY stage_web.py ./
COPY web-source ./web-source
RUN python stage_web.py

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home planner && mkdir -p /app/data && chown -R planner:planner /app
COPY --chown=planner:planner server/server.py server/admin.py /app/
COPY --from=web-build --chown=planner:planner /source/server/web /app/web
USER planner
ENV PLANNER_HOST=0.0.0.0 PLANNER_PORT=8080 PLANNER_DB=/app/data/planner.sqlite PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "server.py"]
