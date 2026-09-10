FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Berlin

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# The venv lives outside /timetable so the development bind mount of the
# source tree cannot shadow it with the host's virtual environment.
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /timetable

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["waitress-serve", "--listen=0.0.0.0:8080", "trains:app"]