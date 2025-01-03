#!/bin/bash

# Script to inline include statements in a Makefile

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <Makefile>"
    exit 1
fi

makefile=$1
tempfile=$(mktemp)

# Ensure tempfile will be deleted on script exit
trap "rm -f $tempfile" EXIT

# Check each line of the Makefile
while IFS= read -r line
do
    # Check if the line starts with 'include'
    if [[ "$line" =~ ^include\  ]]; then
        # Extract the filename, assuming no spaces in filenames
        include_file=$(echo "$line" | cut -d' ' -f2-)
        # Check if the included file exists
        if [ -f "$include_file" ]; then
            # Append the content of the include file to the temp file
            cat "$include_file" >> "$tempfile"
        else
            echo "Warning: Included file $include_file not found."
        fi
    else
        # Append the original line to the temp file
        echo "$line" >> "$tempfile"
    fi
done < "$makefile"

# Move the tempfile to the original makefile name (or another name as needed)
mv "$tempfile" "$makefile.flattened"
echo "Flattened Makefile is available at $makefile.flattened"
