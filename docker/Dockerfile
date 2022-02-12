FROM alpine:3.15

COPY . /pinger

WORKDIR /pinger

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "-u", "pinger.py" ]