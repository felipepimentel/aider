#!/bin/bash

# Set environment variables
export STACKSPOTAI_CLIENT_ID=fake_client_id
export STACKSPOTAI_CLIENT_KEY=fake_client_key
export STACKSPOTAI_REMOTEQC_NAME=fake_remote_qc
export STACKSPOTAI_REALM=stackspot

# Set test mode and force interactive
export AIDER_TEST_MODE=1
export PYTHONUNBUFFERED=1
export FORCE_INTERACTIVE=1
export TERM=xterm-256color

# Run aider with debug flags
poetry run aider --verbose --fancy-input

# Check the exit code
exit_code=$?

# Print the result
if [ $exit_code -eq 0 ]; then
    echo "Test completed successfully"
else
    echo "Test failed with exit code $exit_code"
fi 