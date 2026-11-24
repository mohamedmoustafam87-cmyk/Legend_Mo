"""Edit only previously accepted private report messages. Never creates messages."""
import base64,hashlib,json,os,sys,urllib.request,urllib.error
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def main():
    token=os.environ['TELEGRAM_TOKEN'].strip();destination=os.environ['ADMIN_CHAT_ID'].strip();gh=os.environ['GH_TOKEN'].strip();repo=os.environ['GITHUB_REPOSITORY']
    aes=AESGCM(hashlib.sha256(token.encode()).digest())
    def decode(blob,aad):return json.loads(aes.decrypt(blob[:12],blob[12:],aad))
    request=decode(base64.b64decode(json.loads(Path('reviewed_private_edit.enc.json').read_text())['payload']),b'LegendMo-private-edit-v1')
    def api(path):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,headers={'Authorization':'Bearer '+gh,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
    def telegram(method,body):
        if method not in ('getChat','editMessageText'):raise ValueError('Edit only')
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            try:data=json.load(e)
            except Exception:raise ValueError('Telegram rejection')
            if e.code==400 and 'message is not modified' in data.get('description',''):return {'ok':True,'unchanged':True}
            raise ValueError('Telegram rejection')
    chat=telegram('getChat',{'chat_id':destination})
    if not chat.get('ok') or chat.get('result',{}).get('type')!='private' or str(chat['result']['id'])!=destination:raise ValueError('Private validation failed')
    f=api('/contents/private-delivery-state.enc?ref=delivery-state');state=decode(base64.b64decode(f['content']),b'LegendMo-journal-v1')
    texts=request['messages'];batch=request['original_batch_id']
    if len(texts)!=6 or any(len(t.encode('utf-16-le'))//2>3800 for t in texts):raise ValueError('Edit bounds')
    ids=[]
    for i in range(len(texts)):
        row=state.get(batch+':'+str(i))
        if not row or row.get('status')!='sent' or not row.get('message_id'):raise ValueError('No accepted original')
        ids.append(row['message_id'])
    for i,(identity,text) in enumerate(zip(ids,texts)):
        response=telegram('editMessageText',{'chat_id':destination,'message_id':identity,'text':text})
        if not response.get('ok'):raise ValueError('Edit unconfirmed')
        print('Part',i+1,'edited' if not response.get('unchanged') else 'already current','message_id='+str(identity))
    print('COMPLETE: six existing private report messages updated. Zero new messages.')


if __name__=='__main__':
    try:main()
    except Exception as e:print('Edit stopped. Category:',type(e).__name__,'. No new message created.');sys.exit(1)
