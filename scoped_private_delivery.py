"""Manual encrypted private-report delivery, durable claims, no ambiguous retry."""
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def main():
    token=os.environ['TELEGRAM_TOKEN'].strip()
    destination=os.environ['ADMIN_CHAT_ID'].strip()
    gh=os.environ['GH_TOKEN'].strip()
    repo=os.environ['GITHUB_REPOSITORY']
    from pathlib import Path
    supplied=json.loads(Path('reviewed_private_batch.enc.json').read_text())
    batch=supplied['batch_id']
    key=hashlib.sha256(token.encode()).digest()
    aes=AESGCM(key)
    data=base64.b64decode(supplied['encrypted_payload'])
    payload=json.loads(aes.decrypt(data[:12],data[12:],b'LegendMo-private-report-v1'))
    raw=json.dumps(payload,ensure_ascii=False).encode()
    if hashlib.sha256(raw).hexdigest()!=batch:raise ValueError('Batch mismatch')
    messages=payload['messages']
    if not messages or any(len(t.encode('utf-16-le'))//2>3800 for t in messages):raise ValueError('Part bounds')
    if not destination.isdecimal():raise ValueError('Private destination format')
    def api(path,values=None,method='GET'):
        headers={'Authorization':'Bearer '+gh,'Accept':'application/vnd.github+json'}
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,headers=headers,data=json.dumps(values).encode() if values is not None else None,method=method)
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    def telegram(method,values):
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,data=json.dumps(values).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    chat=telegram('getChat',{'chat_id':destination})
    if not chat.get('ok') or chat.get('result',{}).get('type')!='private' or str(chat['result']['id'])!=destination:raise ValueError('Private binding failed')
    print('Configured private destination verified. No ID or report content logged.')
    branch='delivery-state'
    try:api('/git/ref/heads/'+branch)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        head=api('/git/ref/heads/main')['object']['sha']
        api('/git/refs',{'ref':'refs/heads/'+branch,'sha':head},'POST')
    path='private-delivery-state.enc'
    file_sha=None;state={}
    try:
        f=api('/contents/'+path+'?ref='+branch);file_sha=f['sha'];blob=base64.b64decode(f['content']);state=json.loads(aes.decrypt(blob[:12],blob[12:],b'LegendMo-journal-v1'))
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    def persist():
        nonlocal file_sha
        nonce=os.urandom(12);cipher=nonce+aes.encrypt(nonce,json.dumps(state).encode(),b'LegendMo-journal-v1')
        body={'message':'Update encrypted private delivery state','content':base64.b64encode(cipher).decode(),'branch':branch}
        if file_sha:body['sha']=file_sha
        result=api('/contents/'+path,body,'PUT');file_sha=result['content']['sha']
    receipts=[]
    for i,text in enumerate(messages):
        identity=batch+':'+str(i)
        previous=state.get(identity)
        if previous:
            if previous['status']=='sent':
                receipts.append(previous['message_id']);print('Part',i+1,'already accepted; skipped');continue
            raise ValueError('Prior ambiguous claim, manual reconciliation required')
        state[identity]={'status':'claimed'};persist()
        # No retry once a claim is persisted. Timeout is ambiguous forever
        # until a human checks receipt, preventing duplicate private reports.
        response=telegram('sendMessage',{'chat_id':destination,'text':text})
        r=response.get('result',{})
        if not response.get('ok') or str(r.get('chat',{}).get('id'))!=destination or not r.get('message_id'):raise ValueError('Delivery unconfirmed')
        state[identity]={'status':'sent','message_id':r['message_id'],'date':r.get('date')};persist();receipts.append(r['message_id'])
        print('Part',i+1,'accepted. message_id='+str(r['message_id'])+' date='+str(r.get('date')))
    print('COMPLETE',len(receipts),'private report parts accepted. No scheduled dispatch enabled.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never print HTTP exception URL: it may contain a Telegram credential.
        print('Stopped safely. Category:',type(error).__name__,'. No automatic send retry.');sys.exit(1)
