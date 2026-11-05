"""Real native HTTP negative controls. Requires the service-http fixture script."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid


def main():
    base = os.environ['BATTERY_NATIVE_URL']
    credentials = base64.b64encode((os.environ['BATTERY_NATIVE_USER'] + ':' + os.environ['BATTERY_NATIVE_PASSWORD']).encode()).decode()
    def call(path, body=None, operator='service-quota-test', auth=True):
        headers={'X-Battery-Operator':operator, 'Content-Type':'application/json'}
        if auth: headers['Authorization']='Basic '+credentials
        req=Request(base+path, headers=headers, data=None if body is None else json.dumps(body).encode())
        try:
            with urlopen(req, timeout=10) as response: return response.status,json.load(response)
        except HTTPError as ex:
            return ex.code,None
    code,items=call('/cases')
    assert code==200 and not any(r['id']=='service-http-foreign' for r in items['items'])
    assert call('/cases/service-http-foreign')[0]==404
    assert call('/cases',auth=False)[0]==401
    case={'id':'quota-'+str(uuid.uuid4()),'rule':'one receipt','expected':'complete','acceptance':'complete','observed':'unavailable','facts':{'F1':'No evidence'}}
    contract={'profile':'receipt-v1','partner':'service-quota-test','attempt':'fixture','target':'fixture','version':'1','rule_version':'1','expected_count':1,'expected_result':'COMPLETE','accepted_count':1,'accepted_result':'COMPLETE','max_age':300}
    body={'case':case,'contract':contract,'initial':{'available':False},'parent_id':''}
    assert call('/cases',body,operator='forged-operator')[0]==403
    original=case['id']
    case['id']='service-http-foreign'
    assert call('/cases',body)[0]==404
    case['id']='service-http-replay'
    replay_code,replay=call('/cases',body)
    assert replay_code==200 and replay['state']=='HELD_FOR_EVIDENCE'
    case['id']=original
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses=list(pool.map(lambda _:call('/cases',body)[0],range(8)))
    assert statuses==[429]*8,statuses
    assert call('/cases/'+case['id'])[0]==404
    report={'scope':'real native password-authenticated HTTP against disposable quota/foreign-owner fixtures; no model or business effects', 'foreign_owner_list_hidden':True,'foreign_owner_get':404,'anonymous':401,'operator_contract_mismatch':403,'concurrent_exhausted_budget_statuses':statuses,'rejected_case_not_created':True,'foreign_owner_replay':404,'replay_at_exhausted_budget':200}
    Path('/app/var/service-http-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SERVICE_HTTP_OK',flush=True)

if __name__=='__main__': main()
