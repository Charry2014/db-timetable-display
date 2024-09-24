FROM ubuntu:24.04

EXPOSE 8080

RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get install -y curl
RUN apt-get install -y git python3 python3-pip python3-venv

ENV WORKDIR=/timetable
ENV VENV=$WORKDIR/venv

WORKDIR $WORKDIR
RUN python3 -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

COPY ./db-timetable-display/ $WORKDIR/db-timetable-display/
WORKDIR $WORKDIR/db-timetable-display
RUN pip3 install -r requirements.txt

CMD ["${VENV}/bin/waitress-serve", "--listen=0.0.0.0", "trains:app"]