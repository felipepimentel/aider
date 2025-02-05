import json
import os
import time

import requests

STACKSPOTAI_CLIENT_ID = os.environ.get("STACKSPOTAI_CLIENT_ID")
STACKSPOTAI_CLIENT_KEY = os.environ.get("STACKSPOTAI_CLIENT_KEY")
STACKSPOTAI_REMOTEQC_NAME = os.environ.get("STACKSPOTAI_REMOTEQC_NAME")
AUTH_URL = os.environ.get("AUTH_URL")
CREATE_EXEC_URL = os.environ.get("CREATE_EXEC_URL")
CHECK_EXEC_URL = os.environ.get("CHECK_EXEC_URL")
USER_AGENT = os.environ.get("USER_AGENT")

payload = {
    "client_id": STACKSPOTAI_CLIENT_ID,
    "grant_type": "client_credentials",
    "client_secret": STACKSPOTAI_CLIENT_KEY,
}

content_type_map = {
    "json": "application/json",
    "plain": "application/x-www-form-urlencoded",
}


class StackspotAI:
    def __init__(self):
        self.authorization = None

    def _get_headers(self, content_type="json"):
        headers = {
            "Accept": "*/*",
            "User-Agent": USER_AGENT,
            "Content-Type": content_type_map.get(content_type),
        }
        if self.authorization:
            headers["Authorization"] = self.authorization
        return headers

    def _authenticate(self):
        if self.authorization:
            return
        response = requests.post(
            AUTH_URL, headers=self._get_headers("plain"), data=payload
        )
        response.raise_for_status()
        self.authorization = f"Bearer {response.json()['access_token']}"

    def _check_execution(self, execution_id):
        url = f"{CHECK_EXEC_URL}/{execution_id}"
        while True:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            if response.json().get("progress", {}).get("status") == "COMPLETED":
                return response.json()
            time.sleep(2)

    def _start_execution(self, prompt, prompt_template, conversation_id=None):
        suffix_url = f"?conversation_id={conversation_id}" if conversation_id else ""
        data = json.dumps({"input_data": prompt})
        response = requests.post(
            f"{CREATE_EXEC_URL}/{prompt_template}{suffix_url}",
            headers=self._get_headers(),
            data=data,
        )
        response.raise_for_status()
        return response.text.strip('"')

    def chat(
        self, prompt, prompt_template=STACKSPOTAI_REMOTEQC_NAME, conversation_id=None
    ):
        self._authenticate()
        execution_id = self._start_execution(
            prompt=prompt,
            prompt_template=prompt_template,
            conversation_id=conversation_id,
        )
        response = self._check_execution(execution_id)
        return response
