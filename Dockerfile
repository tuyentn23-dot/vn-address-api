FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY data ./data
COPY vn_provinces.json ./
RUN useradd --create-home apiuser
USER apiuser
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
