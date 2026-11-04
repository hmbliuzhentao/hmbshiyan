"""V2.1 integration: admin assignment, producer acceptance/upload and merchant-scoped video review."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v21_assign_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}","JWT_SECRET":"v"*64,
 "ADMIN_EMAIL":"root@example.com","ADMIN_PASSWORD":"test-only-admin-password-123",
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
from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount, BusinessOrder, Video, DATA_DIR, current_user
from app.publish_tasks_v14 import PublishTask, PublishVideo
Base.metadata.create_all(engine)
(work/"videos").mkdir(exist_ok=True)

with SessionLocal() as db:
    admin=User(email="admin@example.com",name="Admin",role="admin",password_hash="test-hash:admin-pass-12345")
    producer_a=User(email="producer-a@example.com",name="Producer A",role="producer",password_hash="test-hash:producer-pass-12345")
    producer_b=User(email="producer-b@example.com",name="Producer B",role="producer",password_hash="test-hash:producer-pass-12345")
    merchant_a=User(email="merchant-a@example.com",name="Merchant A",role="merchant",password_hash="test-hash:merchant-pass-12345")
    merchant_b=User(email="merchant-b@example.com",name="Merchant B",role="merchant",password_hash="test-hash:merchant-pass-12345")
    db.add_all([admin,producer_a,producer_b,merchant_a,merchant_b]);db.flush()
    ma=Merchant(name="Merchant A LLC",status="approved")
    mb=Merchant(name="Merchant B LLC",status="approved")
    db.add_all([ma,mb]);db.flush()
    db.add_all([MerchantAccount(merchant_id=ma.id,user_id=merchant_a.id),MerchantAccount(merchant_id=mb.id,user_id=merchant_b.id)])
    from datetime import date
    order=BusinessOrder(order_no="BM-TEST-A",client_name=ma.name,merchant_id=ma.id,contact="",title="A 产品视频",
        service_type="拍摄+制作+剪辑",owner_id=admin.id,amount_cents=10000,cost_cents=0,status="confirmed",order_date=date.today(),created_by=merchant_a.id)
    db.add(order);db.flush()
    task=PublishTask(order_id=order.id,merchant_id=ma.id,title="A 的 TikTok 制作任务",platform="TikTok",account_label="",instructions="只制作商家 A 的视频",created_by=merchant_a.id)
    db.add(task);db.commit()
    ids={"admin":admin.id,"producer_a":producer_a.id,"producer_b":producer_b.id,"merchant_a":merchant_a.id,"merchant_b":merchant_b.id,"task":task.id}

client=TestClient(app)
def assume(uid):
    def auth():
        with SessionLocal() as db:
            user=db.get(User,uid)
            db.expunge(user)
            return user
    app.dependency_overrides[current_user]=auth

def check(status, method, path, **kwargs):
    r=client.request(method,path,**kwargs)
    assert r.status_code==status,(method,path,status,r.status_code,r.text[:1000])
    return r

# Admin assigns the merchant's task to producer A.
assume(ids["admin"])
r=check(200,"POST",f"/api/staff/publish-tasks/{ids['task']}/assign",json={"assigned_user_id":ids["producer_a"]})
assert r.json()["assigned_user_id"]==ids["producer_a"]
# Producer A sees and accepts; producer B cannot discover the task by listing or guessing its ID.
assume(ids["producer_a"])
r=check(200,"GET","/api/staff/publish-tasks")
assert len(r.json())==1 and r.json()[0]["id"]==ids["task"]
check(200,"POST",f"/api/staff/publish-tasks/{ids['task']}/accept",json={})
assume(ids["producer_b"])
assert check(200,"GET","/api/staff/publish-tasks").json()==[]
check(404,"GET",f"/api/staff/publish-tasks/{ids['task']}")
check(403,"GET","/api/orders")
check(403,"GET","/api/merchants")

# Producer A uploads a real-looking MP4 signature directly to the assigned task.
assume(ids["producer_a"])
video_bytes=b"\x00\x00\x00\x18ftypisom"+b"0"*64
r=check(201,"POST",f"/api/staff/publish-tasks/{ids['task']}/upload",files={"file":("a.mp4",video_bytes,"video/mp4")})
assert r.json()["videos"] and r.json()["status"]=="pending_review"
link_id=r.json()["videos"][0]["id"]
# Producer B cannot stream another producer's assigned task.
assume(ids["producer_b"])
check(404,"GET",f"/api/staff/publish-tasks/{ids['task']}/videos/{link_id}/stream")

# Merchant B cannot see, stream or review Merchant A's task/video.
assume(ids["merchant_b"])
assert check(200,"GET","/api/portal/publish-tasks").json()==[]
check(404,"GET",f"/api/portal/publish-tasks/{ids['task']}")
check(404,"GET",f"/api/portal/publish-tasks/{ids['task']}/videos/{link_id}/stream")
check(404,"POST",f"/api/portal/publish-tasks/{ids['task']}/videos/{link_id}/review",json={"decision":"approved","note":""})

# Merchant A alone can review; the producer sees the rejection and uploads a new version.
assume(ids["merchant_a"])
r=check(200,"POST",f"/api/portal/publish-tasks/{ids['task']}/videos/{link_id}/review",json={"decision":"changes_requested","note":"请补充产品细节镜头"})
assert r.json()["status"]=="changes_requested"
assume(ids["producer_a"])
r=check(200,"POST",f"/api/staff/publish-tasks/{ids['task']}/videos/{link_id}/replace",files={"file":("a-v2.mp4",video_bytes,"video/mp4")})
assert r.json()["status"]=="pending_review" and len(r.json()["videos"])==1
# Merchant A approves the current version; the task becomes approved.
new_link=r.json()["videos"][0]["id"]
assume(ids["merchant_a"])
r=check(200,"POST",f"/api/portal/publish-tasks/{ids['task']}/videos/{new_link}/review",json={"decision":"approved","note":""})
assert r.json()["status"]=="approved"
# Merchant's explicit final confirmation removes physical media but keeps metadata/history.
r=check(200,"POST",f"/api/portal/publish-tasks/{ids['task']}/published",json={"published_url":"https://www.tiktok.com/@merchant/video/123"})
assert r.json()["status"]=="published" and r.json()["videos"][0]["file_deleted"] is True
video_id=r.json()["videos"][0]["video_id"]
with SessionLocal() as db:
    video=db.get(Video,video_id)
    assert video and video.status=="deleted"
    assert not (DATA_DIR/video.storage_key).exists()
check(404,"GET",f"/api/portal/publish-tasks/{ids['task']}/videos/{new_link}/stream")
print("PASS V2.1 admin assignment, producer task isolation, merchant tenant review and post-confirmation media cleanup")
