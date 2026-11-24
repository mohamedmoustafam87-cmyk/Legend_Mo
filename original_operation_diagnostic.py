import os,json,urllib.request,re,base64
b='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY'];h={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}
def api(path,data=None,method='GET'):
 with urllib.request.urlopen(urllib.request.Request(b+path,headers=h,data=json.dumps(data).encode() if data is not None else None,method=method),timeout=25) as f:return json.load(f)
u=b+'/actions/jobs/138485713430/logs'
with urllib.request.urlopen(urllib.request.Request(u,headers=h),timeout=25) as f:logs=f.read().decode()
# Category-only result, no raw provider messages, holdings, secrets or log dump.
category=re.findall(r'Stopped safely:\s*([A-Za-z]+)',logs)
result={'run':45405698162,'failure_categories':category,'original_scanner_finished':'Qualified stocks:' in logs,'portfolio_finished':'Preparing portfolio' in logs,'size_limit_failure':'Original message exceeds Telegram size limit' in logs,'no_retry':True}
raw=json.dumps(result).encode();path='/contents/original-operation-diagnostic.json'
try:prior=api(path+'?ref=delivery-state');sha=prior['sha']
except Exception:sha=None
body={'message':'Record safe original-operation diagnostic category','branch':'delivery-state','content':base64.b64encode(raw).decode()}
if sha:body['sha']=sha
api(path,body,'PUT');print(json.dumps(result))
