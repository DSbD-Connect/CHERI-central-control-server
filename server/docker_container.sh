#!/bin/bash

docker rm -f apache-php-server 1> /dev/null 2> /dev/null
docker run -d -p 80:80 --name apache-php-server -v "$PWD/html":/var/www/html php:8.2-apache
