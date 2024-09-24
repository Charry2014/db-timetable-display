#!/bin/bash

source venv/bin/activate
waitress-serve --listen=0.0.0.0 trains:app


