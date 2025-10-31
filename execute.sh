#!/bin/bash

apt-get update -y && apt-get upgrade -y
apt-get install -y curl git python3 python3-pip python3-venv

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
waitress-serve --listen=0.0.0.0 trains:app


