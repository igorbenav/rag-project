# --------- requirements ---------

FROM python:3.11 AS requirements-stage

WORKDIR /tmp

RUN pip install uv

COPY pyproject.toml /tmp/

RUN uv pip compile pyproject.toml -o requirements.txt


# --------- final image build ---------
FROM python:3.11

WORKDIR /code

COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY src /code/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.interfaces.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
