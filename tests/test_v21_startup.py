"""V2.1 application startup migration and default admin creation smoke test."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v21_startup_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'startup.sqlite3'}","JWT_SECRET":"s"*64,
 "ADMIN_EMAIL":"owner@example.com","ADMIN_PASSWORD":"startup-admin-password-12345",
 "VIDEO_DIR":str(work/"videos"),"SITE_ORIGIN":"http://localhost:8080",
 "COOKIE_SECURE":"false","COOKIE_DOMAIN":"","APP_ENV":"development","OTP_DEBUG":"false",
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
from app.main import app, Base, engine, SessionLocal, User, MerchantAccount, Merchant
Base.metadata.create_all(engine)
with SessionLocal() as db:
    legacy_merchant=User(email=None,phone="+15550001111",name="Legacy Merchant",role="merchant",password_hash="test-hash:legacy-pass")
    db.add(legacy_merchant);db.commit();legacy_merchant_id=legacy_merchant.id

with TestClient(app) as client:
    r=client.get("/api/health")
    assert r.status_code==200 and r.json().get("ok") is True,r.text
    r=client.post("/api/auth/login",json={"identifier":"owner@example.com","password":"startup-admin-password-12345"})
    assert r.status_code==200,r.text
    assert r.json()["role"]=="admin",r.json()
with SessionLocal() as db:
    admins=db.scalars(select(User).where(User.role=="admin",User.is_active.is_(True))).all()
    assert len(admins)==1 and admins[0].email=="owner@example.com"
    membership=db.scalar(select(MerchantAccount).where(MerchantAccount.user_id==legacy_merchant_id))
    assert membership is not None
    assert db.get(Merchant,membership.merchant_id).status=="approved"
print("PASS V2.1 startup, additive migrations, health endpoint and initial admin creation and orphan merchant relinking")
