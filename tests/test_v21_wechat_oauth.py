"""V2.1 WeChat OAuth state, role selection, one-identity-one-account and no role escalation."""
import os, sys, tempfile, types
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

work=Path(tempfile.mkdtemp(prefix="heimanbo_v21_wechat_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}","JWT_SECRET":"w"*64,
 "ADMIN_EMAIL":"root@example.com","ADMIN_PASSWORD":"test-only-admin-password-123",
 "VIDEO_DIR":str(work/"videos"),"SITE_ORIGIN":"http://localhost:8080",
 "COOKIE_SECURE":"false","COOKIE_DOMAIN":"","APP_ENV":"development","OTP_DEBUG":"false",
 "PUBLIC_APP_URL":"http://localhost:8080","WECHAT_APP_ID":"test-app-id","WECHAT_APP_SECRET":"test-app-secret",
 "WECHAT_REDIRECT_URI":"http://localhost:8080/api/auth/wechat/callback",
})
for key in ["POSTGRES_DB","POSTGRES_USER","POSTGRES_PASSWORD"]: os.environ.pop(key,None)
try:
 import pwdlib
except ModuleNotFoundError:
 fake=types.ModuleType("pwdlib")
 class FakeHash:
  @classmethod
  def recommended(cls): return cls()
  def hash(self,s): return "test-hash:"+s
  def verify(self,p,h): return h=="test-hash:"+p
 fake.PasswordHash=FakeHash
 sys.modules["pwdlib"]=fake
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount
import app.v20 as v20
Base.metadata.create_all(engine)
client=TestClient(app, follow_redirects=False)

def start(role):
    r=client.get(f"/api/auth/wechat/start?role={role}")
    assert r.status_code==302,r.text
    state=parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return state

def fake_wechat(code):
    def fn(url):
        if "oauth2/access_token" in url:
            return {"openid": "openid-"+code, "access_token":"access-"+code}
        return {"nickname":"微信用户-"+code}
    return fn

def callback(state, code):
    with patch.object(v20,"wechat_json",side_effect=fake_wechat(code)):
        return client.get("/api/auth/wechat/callback",params={"code":code,"state":state})

# Merchant can self-register immediately, with an approved merchant profile.
merchant_state=start("merchant")
r=callback(merchant_state,"merchant-1")
assert r.status_code==302 and r.headers["location"]=="http://localhost:8080",r.text
with SessionLocal() as db:
    merchant_user=db.scalar(select(User).where(User.name=="微信用户-merchant-1"))
    assert merchant_user and merchant_user.role=="merchant"
    merchant=db.scalar(select(Merchant).join(MerchantAccount,MerchantAccount.merchant_id==Merchant.id).where(MerchantAccount.user_id==merchant_user.id))
    assert merchant and merchant.status=="approved"

# Producer self-registers immediately, but cannot get a merchant account.
producer_state=start("producer")
r=callback(producer_state,"producer-1")
assert r.status_code==302,r.text
with SessionLocal() as db:
    producer=db.scalar(select(User).where(User.name=="微信用户-producer-1"))
    assert producer and producer.role=="producer"
    assert db.scalar(select(func.count(MerchantAccount.id)).where(MerchantAccount.user_id==producer.id))==0

# The same WeChat openid cannot change role by choosing a different role button later.
role_switch_state=start("merchant")
r=callback(role_switch_state,"producer-1")
assert r.status_code==302,r.text
with SessionLocal() as db:
    producer=db.scalar(select(User).where(User.name=="微信用户-producer-1"))
    assert producer.role=="producer"
    assert db.scalar(select(func.count(User.id)).where(User.name=="微信用户-producer-1"))==1

# OAuth state is single-use: replay must not create another account/session.
r=callback(role_switch_state,"producer-1")
assert r.status_code in (302,307) and "wechat_authorization_failed" in r.headers["location"]

# Public callers cannot request an administrator identity.
r=client.get("/api/auth/wechat/start?role=admin")
assert r.status_code==422,r.text
print("PASS V2.1 WeChat merchant/producer registration, auto-activation, role lock and one-time OAuth state")
