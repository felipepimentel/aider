#!/bin/bash

# Set environment variables
export STACKSPOTAI_CLIENT_ID=fake_client_id
export STACKSPOTAI_CLIENT_KEY=fake_client_key
export STACKSPOTAI_REMOTEQC_NAME=fake_remote_qc
export STACKSPOTAI_REALM=stackspot

# Run aider with a simple command
echo "hello" | poetry run aider

# Check the exit code
exit_code=$?

# Print the result
if [ $exit_code -eq 0 ]; then
    echo "Test completed successfully"
else
    echo "Test failed with exit code $exit_code"
fi 