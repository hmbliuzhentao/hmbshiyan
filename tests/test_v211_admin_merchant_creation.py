"""Regression for admin-side merchant onboarding and tenant isolation."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v211_admin_merchant_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}","JWT_SECRET":"x"*64,
 "ADMIN_EMAIL":"root@example.com","ADMIN_PASSWORD":"test-only-admin-password-123",
 "VIDEO_DIR":str(work/"videos"),"SITE_ORIGIN":"http://localhost:8080",
 "COOKIE_SECURE":"false","COOKIE_DOMAIN":"","APP_ENV":"development","OTP_DEBUG":"true",
 "PUBLIC_APP_URL":"http://localhost:8080",
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
from sqlalchemy import select
from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount, apply_v21_migrations
Base.metadata.create_all(engine)
apply_v21_migrations()
with SessionLocal() as db:
    admin=User(email="root@example.com",name="管理员",role="admin",password_hash="test-hash:admin-password-12345")
    db.add(admin); db.commit()

# Public anonymous user still cannot use admin-only creation or ordinary signup.
visitor=TestClient(app)
body={"email":"merchant@example.com","name":"Merchant Owner","merchant_name":"Demo Trading LLC","role":"merchant","password":"strong-password-merchant-123"}
assert visitor.post("/api/users",json=body).status_code in (401,403)
assert visitor.post("/api/auth/register",json={"destination":"a@example.com","code":"123456","name":"A","password":"long-password"}).status_code==410

admin_client=TestClient(app)
r=admin_client.post("/api/auth/login",json={"identifier":"root@example.com","password":"admin-password-12345"})
assert r.status_code==200,r.text
r=admin_client.post("/api/users",json=body)
assert r.status_code==201,r.text
user_id=r.json()["id"]
with SessionLocal() as db:
    user=db.get(User,user_id)
    assert user.role=="merchant"
    assert user.email=="merchant@example.com"
    link=db.scalar(select(MerchantAccount).where(MerchantAccount.user_id==user_id))
    assert link is not None
    merchant=db.get(Merchant,link.merchant_id)
    assert merchant.name=="Demo Trading LLC" and merchant.status=="approved"
    merchant_id=merchant.id

r=admin_client.post("/api/users",json=body)
assert r.status_code==409,r.text

merchant_client=TestClient(app)
r=merchant_client.post("/api/auth/login",json={"identifier":"merchant@example.com","password":"strong-password-merchant-123"})
assert r.status_code==200 and r.json()["role"]=="merchant",r.text
r=merchant_client.get("/api/portal/me")
assert r.status_code==200 and r.json()["id"]==merchant_id,r.text
assert merchant_client.get("/api/merchants").status_code==403
assert merchant_client.post("/api/users",json={"email":"evil@example.com","name":"Not Admin","role":"admin","password":"not-admin-password-123"}).status_code==403
print("PASS V2.1.1 admin merchant onboarding, auto tenant association, login, admin-only controls and public registration disabled")
