FROM python:3.12-slim
ARG APP
ARG INSTALL_TORCH=0
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir numpy 'pydantic>=2.10,<3' 'paho-mqtt>=2.1,<3' 'psycopg[binary]>=3.2,<4' 'scikit-learn>=1.6,<2'
RUN if [ "$INSTALL_TORCH" = 1 ]; then pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch; fi
COPY shared /srv/shared
COPY apps/${APP} /srv/application
ENV PYTHONPATH=/srv:/srv/application
ENV PYTHONUNBUFFERED=1
CMD ["python", "/srv/application/backend/server.py"]
