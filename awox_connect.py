#Thanks a lot to fsaris for the code
#CREDITS: fsaris
#code from
#https://github.com/fsaris/home-assistant-awox/blob/main/custom_components/awox/awox_connect.py


"""Awox connect API"""
import requests
import json
import uuid

AWOX_CONNECT_URL = 'https://l4hparse-prod.awox.cloud/parse/'
AWOX_CONNECT_APPLICATION_ID = '55O69FLtoxPt67LLwaHGpHmVWndhZGn9Wty8PLrJ'
AWOX_CONNECT_CLIENT_KEY = 'PyR3yV65rytEicteNlQHSVNpAGvCByOrsLiEqJtI'


class AwoxConnect:

    def __init__(self, username: str, password: str, installation_id: str = None):
        self._username = username
        self._password = password

        self._object_id = None
        self._session_token = None
        self._installation_id = installation_id

        if not self._installation_id:
            self._installation_id = str(uuid.uuid4())

        self.login()

    def login(self):
        payload = json.dumps({"username": self._username, "password": self._password, "_method": "GET"})

        headers = {
            'x-parse-application-id': AWOX_CONNECT_APPLICATION_ID,
            'x-parse-installation-id': self._installation_id,
            'x-parse-client-key': AWOX_CONNECT_CLIENT_KEY,
            'content-type': 'application/json'
        }

        response = requests.request("POST", AWOX_CONNECT_URL + 'login', headers=headers, data=payload)

        if response.status_code != 200:
            raise Exception('Login failed - %s' % response.json()['error'])

        self._object_id = response.json()['objectId']
        self._session_token = response.json()['sessionToken']

    def _fetch_class(self, class_name: str):
        payload = json.dumps({
            "where":
                {"owner": {"__type": "Pointer", "className": "_User", "objectId": self._object_id}},
            "_method": "GET"
        })
        headers = {
            'x-parse-application-id': AWOX_CONNECT_APPLICATION_ID,
            'x-parse-installation-id': self._installation_id,
            'x-parse-client-key': AWOX_CONNECT_CLIENT_KEY,
            'content-type': 'application/json',
            'x-parse-session-token': self._session_token
        }

        response = requests.request("POST", AWOX_CONNECT_URL + 'classes/' + class_name, headers=headers, data=payload)

        if response.status_code != 200:
            raise Exception('Loading data failed - %s' % response.json()['error'])

        return response.json()['results']

    def credentials(self):
        return self._fetch_class('Credential')[0]

    def devices(self):
        return self._fetch_class('Device')