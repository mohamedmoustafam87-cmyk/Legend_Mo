"""Encrypted GitHub journal with optimistic-lock writes and no send retries.
Shares the existing manual-delivery branch/file and workflow concurrency group.
"""
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PrivateJournal:
    def __init__(self, token, gh, repo):
        self.token, self.gh, self.repo = token, gh, repo
        self.aes = AESGCM(hashlib.sha256(token.encode()).digest())
        self.sha = None
        self.state = {}

    def api(self, path, values=None, method='GET'):
        request = urllib.request.Request('https://api.github.com/repos/'+self.repo+path,
            headers={'Authorization':'Bearer '+self.gh,'Accept':'application/vnd.github+json'},
            data=json.dumps(values).encode() if values is not None else None, method=method)
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    def telegram(self, method, values):
        if method not in ('getChat','sendMessage'):
            raise ValueError('Unsupported Telegram operation')
        request = urllib.request.Request('https://api.telegram.org/bot'+self.token+'/'+method,
            headers={'Content-Type':'application/json'}, data=json.dumps(values).encode(), method='POST')
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    def load(self):
        try:
            self.api('/git/ref/heads/delivery-state')
        except urllib.error.HTTPError as error:
            if error.code != 404: raise
            head = self.api('/git/ref/heads/main')['object']['sha']
            self.api('/git/refs', {'ref':'refs/heads/delivery-state','sha':head}, 'POST')
        try:
            item = self.api('/contents/private-delivery-state.enc?ref=delivery-state')
            self.sha = item['sha']
            blob = base64.b64decode(item['content'])
            self.state = json.loads(self.aes.decrypt(blob[:12],blob[12:],b'LegendMo-journal-v1'))
            if not isinstance(self.state, dict): raise ValueError('Invalid journal')
        except urllib.error.HTTPError as error:
            if error.code != 404: raise
        return self.state

    def persist(self):
        nonce = os.urandom(12)
        blob = nonce+self.aes.encrypt(nonce,json.dumps(self.state).encode(),b'LegendMo-journal-v1')
        body = {'message':'Update encrypted private delivery state',
            'content':base64.b64encode(blob).decode(),'branch':'delivery-state'}
        if self.sha: body['sha'] = self.sha
        result = self.api('/contents/private-delivery-state.enc',body,'PUT')
        self.sha = result['content']['sha']

    def verify_private(self, destination):
        if not destination.isdecimal(): raise ValueError('Private destination format')
        result = self.telegram('getChat', {'chat_id':destination})
        chat = result.get('result',{})
        if not result.get('ok') or chat.get('type') != 'private' or str(chat.get('id')) != destination:
            raise ValueError('Private binding failed')

    def assert_no_ambiguous(self):
        # Includes old manual-part claims as well as new whole-batch claims.
        if any(isinstance(v,dict) and v.get('status')=='claimed' for v in self.state.values()):
            raise ValueError('Ambiguous prior send requires reconciliation; no retry')
