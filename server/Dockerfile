FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home planner && mkdir -p /app/data && chown -R planner:planner /app
COPY --chown=planner:planner server.py admin.py /app/
COPY --chown=planner:planner web /app/web
USER planner
ENV PLANNER_HOST=0.0.0.0 PLANNER_PORT=8080 PLANNER_DB=/app/data/planner.sqlite PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "server.py"]
