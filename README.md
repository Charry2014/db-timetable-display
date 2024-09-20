Read the DB timetables through a third party API and make a nice display of the data. This is designed to be displayed in a card on a Home Assistant dashboard.

If you use Deutsche Bahn trains regularly you will be familiar with the importance of having up-to-date departure information ;-)

# Overview

* The project uses the https://v6.db.transport.rest/ API
* The `requests` module is used to pull data
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

The commands to build and run the container -
`docker build -t timetable .`

`docker run -p5123:8080 -d --restart unless-stopped timetable`


# To-do

Move to docker-compose
Abstract away the station name from the code, as well as the hard coded destinations for the east-west split.
Clean up the time zones
