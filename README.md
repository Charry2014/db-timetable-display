Read the DB timetables through a third party API and make a nice display of the data. This is designed to be displayed in a card on a Home Assistant dashboard.

# Overview

* The `requests` module is used to pull data
* `Flask` is used to create the web page
* The page updates using SSE
* The production site is hosted using `waitress`
* In production the site runs in a Docker container
* The container is hosted on a Proxmox LXC container
* Waitress hosts the site on the standard port 8080 and the Docker command line maps this to 5123


# Introduction

This is an example of reading data from the API, not a very good one as the error handling is very basic and the abstraction is almost non-existant, but the parsing of this is OK and preparing it for display is nice and simple. There's some hard-coded time zone information and the station name, but this project stitches together a few solutions to hidden gotchas.
