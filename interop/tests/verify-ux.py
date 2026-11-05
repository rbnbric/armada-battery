import hashlib,json,os,time,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
base='http://127.0.0.1:8080'
report={'scope':'Installed Battery HTTP and source verification; existing case read only. No model or business operation requested.','checks':[],'hashes':{}}
def check(name,value):
 report['checks'].append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path):
 with client.open(base+path,timeout=10) as response:return response.read(),response.headers
try:
 for i in range(20):
  try: get('/'); break
  except (OSError,urllib.error.URLError):time.sleep(1)
 for name,path in [('static/index.html','/'),('static/app.js','/static/app.js'),('static/app.css','/static/app.css'),('static/battery-logo.png','/static/battery-logo.png')]:
  raw,headers=get(path);expected=Path('/app',name).read_bytes()
  check(name+' HTTP matches installed source',raw==expected)
  report['hashes'][name]=hashlib.sha256(raw).hexdigest()
  check(name+' same-origin CSP',"default-src 'self'" in headers.get('Content-Security-Policy',''))
  if path.endswith('.png'):check('logo MIME',headers['Content-Type']=='image/png')
 report['hashes']['app.py']=hashlib.sha256(Path('/app/app.py').read_bytes()).hexdigest()
 request=urllib.request.Request(base+'/api/session',data=json.dumps({'access_key':os.environ['BATTERY_ACCESS_KEY']}).encode(),headers={'Content-Type':'application/json'})
 with client.open(request,timeout=10) as response:check('operator sign-in',response.status==200)
 raw,_=get('/api/cases');listing=json.loads(raw);check('retained case list',bool(listing.get('items')))
 c=next(c for c in listing['items'] if c['state']=='VERIFIED_MATCH')
 raw,_=get('/api/cases/'+c['id']);case=json.loads(raw)
 check('current task brief',bool(case.get('brief',{}).get('summary')))
 check('completed review has no approval choices',case['brief']['kind']=='COMPLETE' and not case['brief']['choices'])
 check('retained history accessible',bool(case['result'].get('ReviewHistoryJSON')))
 raw,_=get('/api/receipts/'+case['receipt_id']);check('linked receipt accessible',json.loads(raw)['receipt']['id']==case['receipt_id'])
 report['case_id']=case['id'];report['passed']=True
finally:
 Path('/app/var/ux-installed-check.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
