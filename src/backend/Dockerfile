FROM python:3.11

COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y vim
RUN pip install -U pip -i https://mirrors.tencent.com/pypi/simple
RUN pip install wheel==0.45.1 -i https://mirrors.tencent.com/pypi/simple
RUN pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple
