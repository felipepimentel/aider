Run the project using the following command:

```bash
STACKSPOTAI_CLIENT_ID=fake_client_id STACKSPOTAI_CLIENT_KEY=fake_client_key STACKSPOTAI_REMOTEQC_NAME=fake_remote_qc STACKSPOTAI_REALM=stackspot poetry run aider
```

An error is expected to occur during program execution related to token authorization when calling the LLM.

If any other error occurs, you should troubleshoot and resolve the issue.

Note: The token authorization error is expected and part of the normal flow. Any other errors need to be investigated and fixed.

## Project Overview
- aider/__main__.py - Main entry point for the project
- aider/providers/stackspot.py - Stackspot AI client implementation
- aider/providers/stackspot_config.py - Stackspot configuration
- aider/providers/stackspot_constants.py - Stackspot constants

## resources
- hello_world_stackspot.py - Demostrate hello world with stackspot ai
- https://ai.stackspot.com/docs/* - Stackspot AI Documentation
    - https://ai.stackspot.com/docs/quick-commands/create-remote-qc - Create Remote QC
- https://docs.stackspot.com/* - Stackspot Documentation
    - https://docs.stackspot.com/en/home/account/profile/access-token - Access Token Documentation