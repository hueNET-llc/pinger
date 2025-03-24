FROM alpine:3.21 AS build

COPY . /pinger

WORKDIR /pinger

RUN apk add --update --no-cache python3 python3-dev py3-pip gcc musl-dev && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

FROM alpine:3.21

WORKDIR /pinger

COPY --from=build /pinger /pinger
COPY --from=build /usr/lib/python3.12/site-packages/ /usr/lib/python3.12/site-packages/

RUN apk add --update --no-cache python3 fping tzdata

ENTRYPOINT [ "python3", "-u", "pinger.py" ]