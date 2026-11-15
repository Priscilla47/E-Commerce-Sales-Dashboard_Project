# The dashboard and the command line in one image. Build and run: see docs/deployment.md.
FROM python:3.12.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    HOME=/tmp

WORKDIR /app

# The package is installed from its source folder (editable) because the dashboard finds the
# sample file next to the source, in data/. Only the dashboard extra: no test or lint tools.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data/sample_orders.csv ./data/sample_orders.csv
COPY .streamlit ./.streamlit
# No program keeps a setuid or setgid bit: nothing in the container can gain privileges.
RUN pip install -e ".[dashboard]" \
    && groupadd --gid 10001 app \
    && useradd --create-home --uid 10001 --gid 10001 --shell /usr/sbin/nologin app \
    && find / -xdev -type f -perm /6000 -exec chmod a-s {} +

USER 10001:10001

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]

CMD ["streamlit", "run", "src/sales_insights/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
