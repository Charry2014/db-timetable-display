FROM ubuntu:24.04

EXPOSE 8080

RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get install -y curl
RUN apt-get install -y git python3 python3-pip python3-venv

WORKDIR /docker
RUN git clone https://github.com/Charry2014/db-timetable-display
WORKDIR /docker/db-timetable-display

ENV VENV=venv
RUN python3 -m venv $VENV
ENV PATH="$VENV/bin:$PATH"


RUN pip3 install -r requirements.txt
CMD ["./venv/bin/waitress-serve", "--listen=0.0.0.0", "trains:app"]