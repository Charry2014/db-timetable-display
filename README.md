Read the DB timetables through a third party API and make a nice display of the data. This is designed to be displayed in a card on a Home Assistant dashboard.

If you use Deutsche Bahn trains regularly you will be familiar with the importance of having up-to-date departure information ;-)

# Overview

* The project uses the https://v6.db.transport.rest/ API to source train data, not the DB official one
* The `requests` module is used to pull data
* There is some simple caching of previous returned data as the server returns 500 sometimes
* `Flask` is used to create the web page
* The page updates using SSE
* The production site is hosted using `waitress`
* In production the site runs in a Docker container
* The container is hosted on a Proxmox LXC container
* Waitress hosts the site on the standard port 8080 and the Docker command line maps this to 5123


# Introduction

This is an example of reading data from the API, not a very good one as the error handling is very basic and the abstraction is almost non-existant, but the parsing of this is OK and preparing it for display is nice and simple. There's some hard-coded time zone information and the station names, but this project stitches together a few solutions to hidden gotchas.

The official DB API has a number of issues - a developer account is needed to get the authentication keys. The structure of data recieved is very hard to work with and the actual train delay information is hard to find.

# Docker

The container is based on Ubuntu 24.04 and installs Python 3 and pip the usual way. There is a trick with the virtual environment that is doesn't activate in a Docker container the same way it would on a desktop. The `activate` is faked using the PATH variable, but the path to `waitress` has to be given explicitly.

## Dockerfile
The commands to build and run the container -

1. `docker build -t timetable .`
1. `docker run -p5123:8080 -d --restart unless-stopped timetable`

## Docker Compose
Not really sure if this is the best way to do this, fairly sure it is not, but this works even if it is clunky.
The container should again be available on port 5123 but in my testing it remained resolutely on 8080.

Choose a directory on the server and then -

1. `git clone git@github.com:Charry2014/db-timetable-display.git` or `git pull` to update
1. `cp db-timetable-display/docker-compose.yml .`
1. `docker-compose up -d`

Uses the `execute.sh` script to install what is needed and run the server.

# To-do

* Abstract away the station name from the code, as well as the hard coded destinations for the east-west split.
* Clean up the time zones

DONE - Move to docker-compose
