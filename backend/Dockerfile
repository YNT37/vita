FROM python:3.12-slim

WORKDIR /app

# 国内构建加速：Debian / PyPI 镜像
RUN set -eux; \
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
  elif [ -f /etc/apt/sources.list ]; then \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
  fi; \
  apt-get update \
  && apt-get install -y --no-install-recommends gcc libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# SQLite 场景用单 worker，避免写库冲突
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "--timeout", "120", "app:app"]
