#!/bin/bash
set -e

echo "Entrypoint version: $1"

# Clean the build directory
make clean

pip install --upgrade --break-system-packages pip pip-tools
pip-compile --strip-extras --output-file=requirements.txt packages/base_requirements.in
pip install --break-system-packages -r requirements.txt

# Lint with black
make check_format

# Test with pytest
make test

# If you need to keep the container running (for services etc.), uncomment the next line
# tail -f /dev/null
RESULT="🍻🍻🍻 Passed!"

if [[ -n "$GITHUB_OUTPUT" ]]; then
    echo "result=$RESULT" >> "$GITHUB_OUTPUT"
fi
