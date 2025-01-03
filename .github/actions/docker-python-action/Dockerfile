# Use an official Python runtime as a parent image
FROM postgres:14

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Copy entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN apt update && apt install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-protobuf \
    libprotobuf-dev \
    protobuf-compiler \
    build-essential \
    gosu \
    libpq-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

ENV TEST_POSTGRES_USER=postgres
ENV TEST_POSTGRES_DB=postgres_test
ENV TEST_POSTGRES_HOST=localhost
ENV TEST_POSTGRES_PORT=5432
ENV TEST_POSTGRES_HOST_AUTH_METHOD=trust

ENV POSTGRES_USER=postgres
ENV POSTGRES_DB=postgres_test
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432
ENV POSTGRES_HOST_AUTH_METHOD=trust

EXPOSE 6379
EXPOSE 5432

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/entrypoint.sh"]

# Default command for PostgreSQL
CMD ["postgres"]
