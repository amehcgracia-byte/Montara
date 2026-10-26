import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from flask import Flask
from private_access import PrivateAccess, AccessError, register_private_access

@pytest.fixture
def access(tmp_path):
    now=[100000.]
    return PrivateAccess(tmp_path/'private.sqlite',clock=lambda:now[0]),now

def test_invite_is_private_bound_single_use_and_revocable(access):
    store,now=access
    invite=store.invite('Tester one')
    assert invite['token'] not in json.dumps(store.report())
    with store.transaction() as db:
        assert invite['token'] not in str([tuple(r) for r in db.execute('SELECT * FROM invitations')])
    assert store.entitlement('other') is None
    with pytest.raises(AccessError):store.redeem(invite['token'],None)
    entitlement=store.redeem(invite['token'],'provider|one')
    assert entitlement['plan']=='internal' and entitlement['price_eur']==0
    assert entitlement['commercial_quota_exempt'] and not entitlement['admin']
    assert entitlement['hardware']=='available_only'
    with pytest.raises(AccessError):store.redeem(invite['token'],'provider|two')
    assert store.entitlement('provider|two') is None
    store.revoke(invite['id']);assert store.entitlement('provider|one') is None

def test_invite_expiry_grant_expiry_and_concurrent_redemption(access):
    store,now=access
    invite=store.invite('Expired');now[0]+=8*86400
    with pytest.raises(AccessError):store.redeem(invite['token'],'one')
    invite=store.invite('Race',access_days=1)
    def redeem(account):
        try:return store.redeem(invite['token'],account)
        except AccessError:return None
    with ThreadPoolExecutor(2) as executor:results=list(executor.map(redeem,['one','two']))
    assert sum(x is not None for x in results)==1
    now[0]+=86400
    assert store.entitlement('one') is None and store.entitlement('two') is None

def test_usage_is_metered_even_when_free_and_retry_is_idempotent(access):
    store,_=access
    store.redeem(store.invite('Load test')['token'],'tester')
    assert store.record_usage('tester','render1','cost_eur',.02)
    assert not store.record_usage('tester','render1','cost_eur',.02)
    with pytest.raises(AccessError):store.record_usage('tester','render1','cost_eur',.04)
    with pytest.raises(AccessError):store.record_usage('tester','render2','cpu_seconds',float('nan'))
    assert store.report()['usage'][0]['amount']==.02

def test_http_uses_verified_identity_and_never_browser_account(access):
    store,_=access;app=Flask(__name__);identity=[None]
    register_private_access(app,store,lambda:identity[0]);client=app.test_client()
    token=store.invite('Signed in tester')['token']
    assert client.post('/montara/account/invitation',json={'token':token,'account':'owner'}).status_code==401
    identity[0]='provider|tester'
    assert client.post('/montara/account/invitation',json={'token':token},headers={'Origin':'https://other.test'}).status_code==403
    response=client.post('/montara/account/invitation',json={'token':token,'account':'owner'},headers={'Origin':'http://localhost'})
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    assert store.entitlement('owner') is None
    assert client.get('/montara/account/access').json['access']['role']=='tester'
    assert client.post('/montara/account/invitation',json={'token':token},headers={'Origin':'http://localhost'}).status_code==400
