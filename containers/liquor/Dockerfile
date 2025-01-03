# Use the official Python 3.12 image as the base image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

RUN apt-get update && \
    apt-get install -y make && \
    rm -rf /var/lib/apt/lists/*

RUN make install

RUN make lint