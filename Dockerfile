FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["python", "-m", "orbitronops_postmortem"]
CMD ["generate", "examples/incident-oomkilled.json"]
