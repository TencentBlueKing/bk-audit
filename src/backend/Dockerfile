FROM python:3.10

COPY . /app

WORKDIR /app

RUN pip install -U pip -i https://mirrors.tencent.com/pypi/simple
RUN pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple
