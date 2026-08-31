# 1. Usa uma imagem base oficial do Python, versão slim para economizar espaço
FROM python:3.11-slim

# 2. Configurações de ambiente do Python para rodar melhor no Docker
# Evita a criação de arquivos de cache .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Garante que os logs (prints) apareçam em tempo real no terminal
ENV PYTHONUNBUFFERED=1

# 3. Define a pasta principal dentro do container
WORKDIR /workspace

# 4. Copia apenas o arquivo de requisitos primeiro (Otimização de cache do Docker)
COPY requirements.txt .

# 5. Instala as bibliotecas do Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o restante dos arquivos da pasta app/ para dentro do container
COPY app/ ./app/

# 7. Comando que mantém o container vivo rodando o script principal
CMD ["python", "app/telegram_listener.py"]
