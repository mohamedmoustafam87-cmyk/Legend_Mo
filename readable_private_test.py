"""One explicitly requested readable-format private transport test, no market fetch."""
import os,json,base64,hashlib,sys
from pathlib import Path
from private_journal import PrivateJournal


def main():
    token=os.environ['TELEGRAM_TOKEN'].strip()
    journal=PrivateJournal(token,os.environ['GH_TOKEN'].strip(),os.environ['GITHUB_REPOSITORY'])
    envelope=json.loads(Path('readable_private_test.enc.json').read_text())
    blob=base64.b64decode(envelope['payload'])
    payload=json.loads(journal.aes.decrypt(blob[:12],blob[12:],b'LegendMo-readable-test-v1'))
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    if hashlib.sha256(raw).hexdigest()!=envelope['identity']:raise ValueError('Identity mismatch')
    messages=payload['messages']
    if not messages or len(messages)>10 or any(not isinstance(t,str) or len(t.encode('utf-16-le'))//2>3800 for t in messages):raise ValueError('Bounds')
    destination=os.environ['ADMIN_CHAT_ID'].strip()
    journal.load();journal.assert_no_ambiguous();journal.verify_private(destination)
    identity='readable-test:'+envelope['identity']
    if identity in journal.state:
        if journal.state[identity].get('status')=='sent':
            print('Already accepted test; no duplicate send.');return
        raise ValueError('Prior ambiguous test')
    journal.state[identity]={'status':'claimed','request':payload['request'],'receipts':[]}
    journal.persist()
    for index,text in enumerate(messages):
        result=journal.telegram('sendMessage',{'chat_id':destination,'text':text})
        r=result.get('result',{})
        if not result.get('ok') or str(r.get('chat',{}).get('id'))!=destination or not r.get('message_id'):raise ValueError('Unconfirmed')
        journal.state[identity]['receipts'].append({'part':index+1,'message_id':r['message_id'],'date':r.get('date')})
        journal.persist()
        print('Accepted private test part',index+1,'message_id',r['message_id'],'date',r.get('date'))
    journal.state[identity]['status']='sent';journal.persist()
    print('COMPLETE',len(messages),'readable private test parts; no market calls or schedule changes.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Stopped safely:',type(error).__name__,'. No automatic retry.');sys.exit(1)
