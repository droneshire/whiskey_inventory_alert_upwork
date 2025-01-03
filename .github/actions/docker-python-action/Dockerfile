# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Copy entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN apt update && apt install -y --no-install-recommends \
    build-essential \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/entrypoint.sh"]
