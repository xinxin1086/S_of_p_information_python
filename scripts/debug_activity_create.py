import requests
import json
base='http://127.0.0.1:5000'
admin_login = requests.post(base+'/api/user/auth/login', json={'account':'admin','password':'123456'})
print('login', admin_login.status_code, admin_login.text)
if admin_login.status_code!=200:
    raise SystemExit('login failed')
token = admin_login.json().get('data', {}).get('token') or admin_login.json().get('token')
headers={'Authorization':f'Bearer {token}'}
payload={'title':'Dbg','description':'d','location':'loc','start_time':'2099-01-01T00:00:00Z','end_time':'2099-01-02T00:00:00Z','max_participants':10,'status':'published'}
r = requests.post(base+'/api/activities/admin/activities', json=payload, headers=headers)
print('create', r.status_code)
print(r.text)
