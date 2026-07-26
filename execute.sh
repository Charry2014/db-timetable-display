#!/bin/bash

apt-get update -y && apt-get upgrade -y
apt-get install -y curl git python3 python3-pip python3-venv wget gnupg

python3 -m venv venv
source venv/bin/activate

wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | \
    gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] \
https://dl.google.com/linux/chrome/deb/ stable main" | \
tee /etc/apt/sources.list.d/google-chrome.list

apt-get update -y
apt-get install -y google-chrome-stable

pip install -r requirements.txt
exec waitress-serve --listen=0.0.0.0:8180 trains:app


