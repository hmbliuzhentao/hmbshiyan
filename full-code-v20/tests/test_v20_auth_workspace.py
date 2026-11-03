"""V2.0 smoke tests: OTP registration, sessions and merchant workspace isolation."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v20_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}","JWT_SECRET":"x"*64,
 "ADMIN_EMAIL":"root@example.com","ADMIN_PASSWORD":"test-only-admin-password-123",
 "VIDEO_DIR":str(work/"videos"),"SITE_ORIGIN":"http://localhost:8080",
 "COOKIE_SECURE":"false","COOKIE_DOMAIN":"","APP_ENV":"development","OTP_DEBUG":"true",
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
from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount, PASSWORD
from app.v20 import WorkspaceItem, UserSession
Base.metadata.create_all(engine)
client=TestClient(app)
r=client.post("/api/auth/otp/request",json={"destination":"one@example.com","purpose":"register"})
assert r.status_code==200,r.text
code=r.json()["debug_code"]
r=client.post("/api/auth/register",json={"destination":"one@example.com","code":code,"password":"merchant-pass-12345","name":"Merchant One","merchant_name":"Merchant One LLC"})
assert r.status_code==201,r.text
assert r.json()["user"]["role"]=="merchant"
with SessionLocal() as db:
 m1=db.scalar(select(Merchant).where(Merchant.name=="Merchant One LLC"))
 m1_id=m1.id
 admin=User(email="root@example.com",name="System Admin",role="admin",
            password_hash=PASSWORD.hash("test-only-admin-password-123"))
 db.add(admin)
 u2=User(email="two@example.com",name="Merchant Two",role="merchant",password_hash=PASSWORD.hash("merchant-pass-12345"))
 db.add(u2);db.flush()
 m2=Merchant(name="Merchant Two LLC",status="approved")
 db.add(m2);db.flush()
 db.add(MerchantAccount(merchant_id=m2.id,user_id=u2.id))
 db.commit()
# administrator must explicitly approve a self-registered merchant before ordering.
r=client.post("/api/auth/login",json={"identifier":"root@example.com","password":"test-only-admin-password-123"})
assert r.status_code==200,r.text
r=client.post(f"/api/merchants/{m1_id}/review",json={"decision":"approved","reason":"verified test merchant"})
assert r.status_code==200 and r.json()["status"]=="approved",r.text
r=client.post(f"/api/merchants/{m1_id}/review",json={"decision":"rejected","reason":"after approval"})
assert r.status_code==409,r.text
# first merchant creates a product item
r=client.post("/api/auth/login",json={"identifier":"one@example.com","password":"merchant-pass-12345"})
assert r.status_code==200,r.text
r=client.post("/api/workspace/product",json={"title":"Merchant One Product","body":"private A"})
assert r.status_code==201,r.text
r=client.get("/api/workspace/product")
assert r.status_code==200 and r.json()["total"]==1,r.text
r=client.get("/api/auth/sessions")
assert r.status_code==200 and len(r.json())>=1,r.text
# second merchant must not see merchant one's product
client2=TestClient(app)
r=client2.post("/api/auth/login",json={"identifier":"two@example.com","password":"merchant-pass-12345"})
assert r.status_code==200,r.text
r=client2.get("/api/workspace/product")
assert r.status_code==200 and r.json()["total"]==0,r.text
# user from another merchant cannot update known item id
r=client2.patch("/api/workspace/product/1",json={"title":"hacked"})
assert r.status_code==404,r.text
# Contact binding and password reset are OTP-gated.
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
r=client.post("/api/auth/login",json={"identifier":"one+bound@example.com","password":"new-merchant-pass-12345"})
assert r.status_code==200,r.text
print("PASS V2 OTP registration, contact binding, password reset, sessions and merchant tenant isolation")
# Account creation is limited to three types: admin, producer, merchant.
# Merchant accounts have their own registration flow; admins cannot create them in /users.
admin_client=TestClient(app)
r=admin_client.post("/api/auth/login",json={"identifier":"root@example.com","password":"test-only-admin-password-123"})
assert r.status_code==200,r.text
r=admin_client.post("/api/users",json={"email":"camera@example.com","name":"Camera and Editing",
                                        "password":"test-only-producer-password","role":"producer"})
assert r.status_code==201 and r.json()["role"]=="producer",r.text
producer_id=r.json()["id"]
for invalid in ("manager","viewer","editor","merchant","super_admin"):
 r=admin_client.post("/api/users",json={"email":f"invalid-{invalid}@example.com","name":"Invalid role",
                                         "password":"test-only-producer-password","role":invalid})
 assert r.status_code==400,(invalid,r.text)
r=admin_client.patch(f"/api/users/{producer_id}/role",json={"role":"admin"})
assert r.status_code==200 and r.json()["role"]=="admin",r.text
r=admin_client.patch(f"/api/users/{producer_id}/role",json={"role":"producer"})
assert r.status_code==200 and r.json()["role"]=="producer",r.text
r=admin_client.patch("/api/users/1/role",json={"role":"producer"})
assert r.status_code==403,r.text  # merchant cannot become internal staff
producer_client=TestClient(app)
r=producer_client.post("/api/auth/login",json={"identifier":"camera@example.com",
                                              "password":"test-only-producer-password"})
assert r.status_code==200,r.text
for path in ("/api/users","/api/orders/stats","/api/orders","/api/merchants"):
 r=producer_client.get(path)
 assert r.status_code==403,(path,r.text)
r=producer_client.get("/api/staff/projects")
assert r.status_code==200,r.text
r=producer_client.get("/api/staff/publish-tasks")
assert r.status_code==200,r.text
r=producer_client.post("/api/workspace/script",json={"title":"Production script","body":"Production team only"})
assert r.status_code==201,r.text
r=producer_client.get("/api/portal/orders")
assert r.status_code==403,r.text
print("PASS V2 three-account model and producer/admin/merchant authorization")

