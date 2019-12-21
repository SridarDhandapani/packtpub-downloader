# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import requests
import json
from config import BASE_URL, AUTH_ENDPOINT, AUTH_REFRESH_ENDPOINT


class User:
    """
        User object that contain his header
    """
    username = ""
    password = ""
    access = ""
    refresh = ""
    # need to fill Authoritazion with current token provide by api
    header = {}
    header["User-Agent"] = "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36" #!yapf: disable
    header["Authorization"] = ""

    def __init__(self, *args, **kwargs):
        if kwargs.get('file', None):
            self.username = kwargs['username']
            self.password = kwargs['password']
            self.header["Authorization"] = self.get_token()
        else:
            self.read_token()
            self.header['Authorization'] = self.refresh_token()

    def read_token(self):
        with open('token.json', 'r') as f:
            data = json.load(f)
            self.access = data['access']
            self.refresh = data['refresh']
            self.header['Authorization'] = 'Bearer ' + self.access

    def save_token(self, data):
        with open('token.json', 'w') as f:
            json.dump(data, f)
        self.access = data['access']
        self.refresh = data['refresh']

    def get_token(self):
        """
            Request auth endpoint and return user token
        """
        url = BASE_URL + AUTH_ENDPOINT
        # use json paramenter because for any reason they send user and pass in plain text :'(
        r = requests.post(
            url, json={
                'username': self.username,
                'password': self.password
            })
        if r.status_code == 200:
            print("You are in!")
            self.save_token(r.json()['data'])
            return 'Bearer ' + self.access

        # except should happend when user and pass are incorrect
        print("Error login,  check user and password")
        print("Error {}".format(r.json()))
        sys.exit(2)

    def refresh_token(self):
        """
            Refresh endpoint; return user token & refresh token
        """
        url = BASE_URL + AUTH_REFRESH_ENDPOINT
        # use json paramenter because for any reason they send user and pass in plain text :'(
        r = requests.post(
            url,
            json={
                'refresh': self.refresh,
            },
            headers=self.get_header())
        if r.status_code == 200:
            print("Token refreshed!")
            self.save_token(r.json()['data'])
            return 'Bearer ' + self.access

        # except should happend when user and pass are incorrect
        print("Error login,  check access & refresh tokens in token.json")
        print("Error {}".format(r.json()))
        sys.exit(2)

    def get_header(self):
        return self.header

    def refresh_header(self):
        """
            Refresh jwt because it expired and returned
        """
        self.refresh_token()
        self.header["Authorization"] = self.refresh_token()

        return self.header
