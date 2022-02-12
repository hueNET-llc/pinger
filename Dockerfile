FROM alpine:3.15

COPY . /pinger

WORKDIR /pinger

RUN apk add python3 python3-dev py3-pip gcc musl-dev fping && pip install -r requirements.txt

ENTRYPOINT [ "python3", "-u", "pinger.py" ]