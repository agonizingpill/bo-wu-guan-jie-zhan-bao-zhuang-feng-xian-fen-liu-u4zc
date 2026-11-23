import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .schemas import Role, StaffMember
from .storage import connection

bearer = HTTPBearer(auto_error=False)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f'{salt}:{digest.hex()}'


def verify_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(':', 1)[0]), stored)


def issue_token(account):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': account.username, 'role': account.role, 'iat': now,
                       'exp': now + timedelta(hours=8), 'iss': 'museum-crate-triage'},
                      os.environ['JWT_SECRET'], algorithm='HS256')


def signed_in(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, '请先登录', headers={'WWW-Authenticate': 'Bearer'})
    try:
        claims = jwt.decode(credentials.credentials, os.environ['JWT_SECRET'], algorithms=['HS256'],
                            issuer='museum-crate-triage', options={'require': ['exp', 'sub', 'role']})
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, '登录已过期，请重新登录', headers={'WWW-Authenticate': 'Bearer'}) from exc
    with connection() as db:
        staff = db.execute('SELECT username,display_name,role FROM staff WHERE username=%s',
                           (claims['sub'],)).fetchone()
    if not staff or staff['role'] != claims['role']:
        raise HTTPException(401, '账号角色已变更，请重新登录')
    return StaffMember(**staff)


def require(role: Role):
    def check(staff: StaffMember = Depends(signed_in)):
        if staff.role != role:
            raise HTTPException(403, '当前岗位没有执行该操作的权限')
        return staff
    return check
