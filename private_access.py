"""Private, server-side entitlements. Authentication remains the identity provider's job.

Not connected to demo cookies or browser plan choices. Install the HTTP adapter only
with a verified-account callback, backed by a shared durable database on the server.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROLES = {'owner', 'developer', 'tester'}
FEATURES = ('stage', 'push', 'show', 'gamer', 'influencer', 'story', 'podcast',
            'captions', 'effects', 'music', 'session_audio', 'ai_editing')

class AccessError(ValueError):
    pass

class PrivateAccess:
    def __init__(self, database, clock=time.time):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS invitations (
              id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
              label TEXT NOT NULL, role TEXT NOT NULL, expires REAL NOT NULL,
              grant_seconds INTEGER NOT NULL, redeemed_by TEXT, revoked INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS grants (
              account TEXT PRIMARY KEY, invitation TEXT NOT NULL, role TEXT NOT NULL,
              expires REAL NOT NULL, revoked INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS usage (
              account TEXT NOT NULL, job TEXT NOT NULL, metric TEXT NOT NULL,
              amount REAL NOT NULL, created REAL NOT NULL,
              PRIMARY KEY(account,job,metric));
            CREATE TABLE IF NOT EXISTS audit (
              at REAL NOT NULL, action TEXT NOT NULL, subject TEXT NOT NULL);
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, db, action, subject):
        db.execute('INSERT INTO audit VALUES (?,?,?)', (self.clock(), action, subject))

    def invite(self, label, role='tester', invite_days=7, access_days=30):
        if role not in ROLES or not label.strip():
            raise AccessError('Choose a label and a valid internal role.')
        if not 1 <= invite_days <= 30 or not 1 <= access_days <= 365:
            raise AccessError('Invitation: 1–30 days. Access: 1–365 days.')
        token = secrets.token_urlsafe(32)
        key = secrets.token_hex(16)
        with self.transaction() as db:
            db.execute('INSERT INTO invitations(id,token_hash,label,role,expires,grant_seconds) VALUES (?,?,?,?,?,?)',
                       (key, hashlib.sha256(token.encode()).hexdigest(), label.strip(), role,
                        self.clock() + invite_days*86400, access_days*86400))
            self.audit(db, 'invite.created', key)
        return {'id': key, 'token': token}

    def redeem(self, token, verified_account):
        if not verified_account or not isinstance(verified_account, str):
            raise AccessError('A verified account is required.')
        if not isinstance(token, str) or len(token) > 256:
            raise AccessError('Invitation unavailable.')
        with self.transaction() as db:
            item = db.execute('SELECT * FROM invitations WHERE token_hash=?',
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if not item or item['revoked'] or item['expires'] <= self.clock() or item['redeemed_by']:
                raise AccessError('Invitation unavailable.')
            db.execute('UPDATE invitations SET redeemed_by=? WHERE id=?', (verified_account, item['id']))
            db.execute('INSERT INTO grants VALUES (?,?,?,?,0) ON CONFLICT(account) DO UPDATE SET invitation=excluded.invitation,role=excluded.role,expires=excluded.expires,revoked=0',
                       (verified_account, item['id'], item['role'], self.clock()+item['grant_seconds']))
            self.audit(db, 'invite.redeemed', item['id'])
        return self.entitlement(verified_account)

    def entitlement(self, verified_account):
        with self.transaction() as db:
            grant = db.execute('SELECT g.* FROM grants g JOIN invitations i ON i.id=g.invitation WHERE g.account=? AND g.revoked=0 AND i.revoked=0 AND g.expires>?',
                               (verified_account, self.clock())).fetchone()
        if not grant:
            return None
        return {'plan': 'internal', 'label': 'Acceso interno', 'role': grant['role'],
                'price_eur': 0, 'commercial_quota_exempt': True,
                'features': list(FEATURES), 'expires_at': grant['expires'],
                'admin': False, 'resource_policy': 'metered',
                'hardware': 'available_only', 'priority': 'pro'}

    def revoke(self, invitation):
        with self.transaction() as db:
            row = db.execute('UPDATE invitations SET revoked=1 WHERE id=?', (invitation,))
            if not row.rowcount:
                raise AccessError('Invitation not found.')
            self.audit(db, 'invite.revoked', invitation)

    def record_usage(self, verified_account, job, metric, amount):
        # Call from trusted job completion events, never client-reported cost.
        import math
        if not verified_account or not job or metric not in {'cpu_seconds','gpu_seconds','ai_input_tokens','ai_output_tokens','storage_byte_hours','transfer_bytes','cost_eur'}:
            raise AccessError('Invalid usage event.')
        if isinstance(amount, bool) or not isinstance(amount, (int,float)) or not math.isfinite(amount) or amount < 0:
            raise AccessError('Invalid usage amount.')
        with self.transaction() as db:
            row = db.execute('SELECT amount FROM usage WHERE account=? AND job=? AND metric=?', (verified_account,job,metric)).fetchone()
            if row:
                if row['amount'] != amount:
                    raise AccessError('Conflicting usage event.')
                return False
            db.execute('INSERT INTO usage VALUES (?,?,?,?,?)', (verified_account,job,metric,amount,self.clock()))
            return True

    def report(self):
        # Local administrator only. Tokens and project media never appear here.
        with self.transaction() as db:
            return {'invitations': [dict(r) for r in db.execute('SELECT id,label,role,expires,redeemed_by,revoked FROM invitations')],
                    'usage': [dict(r) for r in db.execute('SELECT account,metric,SUM(amount) AS amount FROM usage GROUP BY account,metric')]}


def register_private_access(app, store, verified_account):
    """Explicit opt-in: callback must resolve a server-verified provider subject.

    No body/header/account ID supplied by the browser is ever used as identity.
    The existing demo intentionally does not register this adapter.
    """
    from flask import jsonify, request

    @app.after_request
    def private_access_no_cache(response):
        if request.path in {'/montara/account/access','/montara/account/invitation'}:
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/montara/account/access')
    def account_access():
        account = verified_account()
        if not account:
            return jsonify(error='Sign in first.'), 401
        return jsonify(access=store.entitlement(account))

    @app.post('/montara/account/invitation')
    def account_invitation():
        account = verified_account()
        if not account:
            return jsonify(error='Sign in first.'), 401
        # The provider session must include CSRF protection; enforce same-origin too.
        if request.headers.get('Origin') != request.host_url.rstrip('/'):
            return jsonify(error='Open this invitation from Montara.'), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error='Invalid invitation request.'), 400
        try:
            access = store.redeem(body.get('token'), account)
        except AccessError as exc:
            return jsonify(error=str(exc)), 400
        response = jsonify(access=access)
        response.headers['Cache-Control'] = 'no-store'
        return response


def main():
    parser = argparse.ArgumentParser(description='Montara private access administration (server only)')
    parser.add_argument('--database', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    issue = sub.add_parser('invite')
    issue.add_argument('--label', required=True)
    issue.add_argument('--role', choices=sorted(ROLES), default='tester')
    issue.add_argument('--days', type=int, default=30)
    revoke = sub.add_parser('revoke'); revoke.add_argument('id')
    sub.add_parser('report')
    args = parser.parse_args()
    store = PrivateAccess(args.database)
    if args.action == 'invite':
        print(json.dumps(store.invite(args.label,args.role,access_days=args.days)))
    elif args.action == 'revoke':
        store.revoke(args.id); print('Access revoked.')
    else:
        print(json.dumps(store.report(),indent=2))

if __name__ == '__main__':
    main()
