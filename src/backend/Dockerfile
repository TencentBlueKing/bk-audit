FROM python:3.11@sha256:bdf10582593a61868524172b99150e6aed1b29f2455b4cfb7161643d81a82616

COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y ca-certificates vim
RUN sh bootstrap_pip.sh python
RUN pip install wheel==0.45.1 -i https://mirrors.tencent.com/pypi/simple
RUN pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple
