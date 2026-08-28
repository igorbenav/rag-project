# --------- frontend build ---------
# The React client is compiled here and copied into the API image, so the
# reviewer runs one command and FastAPI serves everything from one origin.

FROM node:22-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# --------- python requirements ---------

FROM python:3.11 AS requirements-stage

WORKDIR /tmp

RUN pip install uv

COPY pyproject.toml /tmp/

RUN uv pip compile pyproject.toml -o requirements.txt


# --------- final image ---------

FROM python:3.11

WORKDIR /code

# Keep .pyc out of the mounted source volume.
ENV PYTHONDONTWRITEBYTECODE=1

COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY backend/src /code/src
COPY --from=frontend /build/dist /code/static

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.interfaces.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
