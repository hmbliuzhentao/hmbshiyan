"""V2.1 regression: WeChat-only public registration, legacy-role migration and merchant tenant isolation."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v21_auth_"))
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
from app.v20 import WorkspaceItem
Base.metadata.create_all(engine)
apply_v21_migrations()

with SessionLocal() as db:
    # Legacy internal roles collapse to the three supported roles without deleting users.
    old_admin=User(email="legacy-root@example.com",name="Legacy Root",role="super_admin",password_hash="test-hash:legacy-password")
    old_manager=User(email="legacy-manager@example.com",name="Legacy Manager",role="manager",password_hash="test-hash:legacy-password")
    old_viewer=User(email="legacy-viewer@example.com",name="Legacy Viewer",role="viewer",password_hash="test-hash:legacy-password")
    db.add_all([old_admin,old_manager,old_viewer])
    db.flush()
    a=User(email="one@example.com",name="Merchant One",role="merchant",password_hash="test-hash:merchant-pass-12345")
    b=User(email="two@example.com",name="Merchant Two",role="merchant",password_hash="test-hash:merchant-pass-12345")
    producer=User(email="producer@example.com",name="Producer",role="producer",password_hash="test-hash:producer-pass-12345")
    db.add_all([a,b,producer]);db.flush()
    ma=Merchant(name="Merchant One LLC",status="approved")
    mb=Merchant(name="Merchant Two LLC",status="approved")
    db.add_all([ma,mb]);db.flush()
    db.add_all([MerchantAccount(merchant_id=ma.id,user_id=a.id),MerchantAccount(merchant_id=mb.id,user_id=b.id)])
    db.commit()
    a_id,b_id,producer_id=a.id,b.id,producer.id

apply_v21_migrations()
with SessionLocal() as db:
    assert db.scalar(select(User).where(User.email=="legacy-root@example.com")).role=="admin"
    assert db.scalar(select(User).where(User.email=="legacy-manager@example.com")).role=="producer"
    assert db.scalar(select(User).where(User.email=="legacy-viewer@example.com")).role=="producer"

client=TestClient(app)
# Email/SMS OTP can still be used for contact binding and password recovery, but not public signup.
r=client.post("/api/auth/otp/request",json={"destination":"new@example.com","purpose":"register"})
assert r.status_code==410,r.text
r=client.post("/api/auth/register",json={"destination":"new@example.com","code":"123456","password":"long-password-12345","name":"Nope"})
assert r.status_code==410,r.text

# Merchant A can only see its own workspace items.
r=client.post("/api/auth/login",json={"identifier":"one@example.com","password":"merchant-pass-12345"})
assert r.status_code==200,r.text
r=client.post("/api/workspace/product",json={"title":"Merchant One Product","body":"private A"})
assert r.status_code==201,r.text
r=client.get("/api/workspace/product")
assert r.status_code==200 and r.json()["total"]==1,r.text
r=client.post("/api/auth/otp/request",json={"destination":"one+bound@example.com","purpose":"bind"})
assert r.status_code==200,r.text
bind_code=r.json()["debug_code"]
r=client.post("/api/auth/contact/bind",json={"destination":"one+bound@example.com","code":bind_code})
assert r.status_code==200 and r.json()["email"]=="one+bound@example.com",r.text
r=client.post("/api/auth/otp/request",json={"destination":"one+bound@example.com","purpose":"password_reset"})
assert r.status_code==200,r.text
reset_code=r.json()["debug_code"]
r=client.post("/api/auth/password/reset",json={"destination":"one+bound@example.com","code":reset_code,"new_password":"new-merchant-pass-12345"})
assert r.status_code==200,r.text

client2=TestClient(app)
r=client2.post("/api/auth/login",json={"identifier":"two@example.com","password":"merchant-pass-12345"})
assert r.status_code==200,r.text
r=client2.get("/api/workspace/product")
assert r.status_code==200 and r.json()["total"]==0,r.text
r=client2.patch("/api/workspace/product/1",json={"title":"hacked"})
assert r.status_code==404,r.text

client3=TestClient(app)
r=client3.post("/api/auth/login",json={"identifier":"producer@example.com","password":"producer-pass-12345"})
assert r.status_code==200,r.text
assert client3.get("/api/workspace/product").status_code==403
assert client3.get("/api/orders").status_code==403
assert client3.get("/api/merchants").status_code==403

# Admin can deactivate/reactivate a producer; the last active admin cannot be disabled.
admin_client=TestClient(app)
r=admin_client.post("/api/auth/login",json={"identifier":"legacy-root@example.com","password":"legacy-password"})
assert r.status_code==200,r.text
r=admin_client.patch(f"/api/users/{producer_id}/active",json={"is_active":False})
assert r.status_code==200 and r.json()["is_active"] is False,r.text
r=admin_client.patch(f"/api/users/{producer_id}/active",json={"is_active":True})
assert r.status_code==200 and r.json()["is_active"] is True,r.text
admin_id=None
with SessionLocal() as db:
    admin_id=db.scalar(select(User).where(User.email=="legacy-root@example.com")).id
r=admin_client.patch(f"/api/users/{admin_id}/active",json={"is_active":False})
assert r.status_code==409,r.text
print("PASS V2.1 three-role migration, WeChat-only public registration, merchant isolation and admin user controls")
