"""Offline integration regression suite for V1.4 using FastAPI TestClient + SQLite.

Use a password-hash stub ONLY inside the test runner where pwdlib is unavailable;
production backend continues using pwdlib's password hashing.
"""
from __future__ import annotations

import os, sys, tempfile, types
from pathlib import Path


def main():
    work=Path(tempfile.mkdtemp(prefix="bm_v14_tests_"))
    os.environ.update({
        "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}",
        "JWT_SECRET":"x"*64,
        "ADMIN_EMAIL":"admin@example.com",
        "ADMIN_PASSWORD":"some-test-only-password-12345",
        "VIDEO_DIR":str(work/"videos"),
        "SITE_ORIGIN":"http://localhost:8080",
        "COOKIE_SECURE":"false",
    })
    for key in ["POSTGRES_USER","POSTGRES_PASSWORD","POSTGRES_DB"]:os.environ.pop(key,None)
    try: import pwdlib
    except ModuleNotFoundError:
        fake=types.ModuleType("pwdlib")
        class MockPasswordHash:
            @classmethod
            def recommended(cls):return cls()
            def hash(self,s):return "stub-hash:"+s
            def verify(self,pw,h):return h=="stub-hash:"+pw
        fake.PasswordHash=MockPasswordHash
        sys.modules["pwdlib"]=fake
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount, BusinessOrder, Video, current_user
    from app.publish_tasks_v14 import PublishTask, PublishVideo, PublishReviewEvent
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin=User(email="admin2@example.com",name="Admin",role="admin",password_hash="hash")
        merchant_user_1=User(email="a@example.com",name="Merchant A",role="merchant",password_hash="hash")
        merchant_user_2=User(email="b@example.com",name="Merchant B",role="merchant",password_hash="hash")
        db.add_all([admin,merchant_user_1,merchant_user_2]);db.flush()
        merchant_a=Merchant(name="Product A")
        merchant_b=Merchant(name="Product B")
        db.add_all([merchant_a,merchant_b]);db.flush()
        assert merchant_a.status=="approved"
        db.add_all([MerchantAccount(merchant_id=merchant_a.id,user_id=merchant_user_1.id),
                    MerchantAccount(merchant_id=merchant_b.id,user_id=merchant_user_2.id)])
        order_a=BusinessOrder(order_no="BM-A1",client_name="Product A",merchant_id=merchant_a.id,title="A订单",service_type="拍摄+剪辑",amount_cents=10000,cost_cents=1000,status="confirmed",order_date=__import__('datetime').date.today())
        order_b=BusinessOrder(order_no="BM-B1",client_name="Product B",merchant_id=merchant_b.id,title="B订单",service_type="拍摄+剪辑",amount_cents=12000,cost_cents=2000,status="confirmed",order_date=__import__('datetime').date.today())
        db.add_all([order_a,order_b]);db.flush()
        vid=Video(id="a-demo-video",filename="product-a.mp4",storage_key="a-demo-video.mp4",mime="video/mp4",size_bytes=24,status="ready",created_by=admin.id)
        db.add(vid);db.commit()
        admin_id, user1_id, user2_id, order_a_id, order_b_id=admin.id, merchant_user_1.id, merchant_user_2.id, order_a.id, order_b.id
    (work/"videos").mkdir(exist_ok=True)
    (work/"videos"/"a-demo-video.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom"+b"0"*16)

    client=TestClient(app)
    def as_role(uid):
        def get_user():
            with SessionLocal() as db:
                user=db.get(User,uid)
                db.expunge(user)
                return user
        app.dependency_overrides[current_user]=get_user
    def request(method,path,**kwargs):
        return client.request(method,path,**kwargs)
    def test(status,response,description):
        assert response.status_code==status, (description,response.status_code,response.text[:800])
        print("PASS:",description)
        return response.json() if response.headers.get("content-type","").startswith("application/json") else response

    as_role(admin_id)
    a=test(201,request("POST","/api/staff/publish-tasks",json={"order_id":order_a_id,"title":"A商品视频发布任务","platform":"TikTok"}),"Admin creates merchant-linked task")
    task_id=a["id"]
    test(400,request("POST","/api/staff/publish-tasks",json={"order_id":999999,"title":"bad"}),"Task requires real order")
    a=test(201,request("POST",f"/api/staff/publish-tasks/{task_id}/videos",json={"video_id":"a-demo-video"}),"Staff attaches already uploaded library video")
    link_id=a["videos"][0]["id"]
    assert a["status"]=="pending_review"
    test(409,request("POST",f"/api/staff/publish-tasks/{task_id}/videos",json={"video_id":"a-demo-video"}),"Prevent duplicate attach")
    test(409,request("DELETE","/api/videos/a-demo-video"),"Bound video cannot be deleted")
    test(409,request("PATCH",f"/api/orders/{order_a_id}",json={"merchant_id":None}),"Order merchant cannot change after publishing task assignment")
    test(410,request("POST", "/api/merchants/1/submit"),"Legacy merchant qualification flow disabled")
    as_role(user2_id)
    assert test(200,request("GET","/api/portal/publish-tasks"),"Other merchant can list its own tasks only")==[]
    test(404,request("GET",f"/api/portal/publish-tasks/{task_id}"),"Merchant B denied A's task")
    test(404,request("GET",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/stream"),"Merchant B cannot stream A's video")
    test(404,request("POST",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/review",json={"decision":"approved"}),"Merchant B cannot approve A's video")
    as_role(user1_id)
    t=test(200,request("GET","/api/portal/publish-tasks"),"Merchant A sees its assigned video")
    assert len(t)==1 and t[0]["videos"][0]["filename"]=="product-a.mp4"
    v=request("GET",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/stream")
    assert v.status_code==200 and v.content.startswith(b"\x00\x00\x00\x18ftyp")
    print("PASS: Merchant A can privately stream assigned video")
    test(400,request("POST",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/review",json={"decision":"changes_requested","note":"no"}),"Revision request requires meaningful note")
    t=test(200,request("POST",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/review",json={"decision":"changes_requested","note":"请突出产品功能"}),"Merchant requests changes")
    assert t["status"]=="changes_requested"
    test(409,request("POST",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/review",json={"decision":"approved"}),"Review cannot be overwritten without new submission")
    as_role(admin_id)
    test(409,request("POST",f"/api/staff/publish-tasks/{task_id}/published",json={}),"Cannot publish before approval")
    new_mp4=b"\x00\x00\x00\x18ftypisom"+b"1"*24
    t=test(200,request("POST",f"/api/staff/publish-tasks/{task_id}/videos/{link_id}/replace",files={"file":("revised.mp4",new_mp4,"video/mp4")}),"Staff uploads revised video for same task")
    assert t["status"]=="pending_review" and len(t["videos"])==1 and t["videos"][0]["filename"]=="revised.mp4"
    new_link_id=t["videos"][0]["id"]
    as_role(user1_id)
    test(404,request("GET",f"/api/portal/publish-tasks/{task_id}/videos/{link_id}/stream"),"Old revision cannot be streamed through superseded link")
    t=test(200,request("POST",f"/api/portal/publish-tasks/{task_id}/videos/{new_link_id}/review",json={"decision":"approved"}),"Merchant A approves new revision")
    assert t["status"]=="approved"
    as_role(admin_id)
    t=test(200,request("POST",f"/api/staff/publish-tasks/{task_id}/published",json={"published_url":"https://www.tiktok.com/@example/video/1"}),"Staff marks approved task as published")
    assert t["status"]=="published"
    test(409,request("POST",f"/api/staff/publish-tasks/{task_id}/videos",json={"video_id":"a-demo-video"}),"Published tasks cannot be changed")
    with SessionLocal() as db:
        events=db.scalars(select(PublishReviewEvent)).all()
        assert len(events)==2 and len(db.scalars(select(PublishVideo)).all())==2
    print("PASS: Review history and superseded video link are preserved")
    print("All V1.4 integration checks passed.")

if __name__=="__main__":main()
