# 1. Usar uma imagem base leve do Python
FROM python:3.10-slim

# 2. Definir o diretório de trabalho dentro do container
WORKDIR /app

# 3. Copiar o arquivo de requisitos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar o resto do código da API
COPY . .

# 5. Expor a porta que o Flask/Gunicorn usará
EXPOSE 5000

# 6. Comando para rodar a aplicação usando Gunicorn (servidor de produção)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]