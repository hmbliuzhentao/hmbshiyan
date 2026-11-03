"""V1.5 integration: merchant owns order and publishing-task creation.

SQLite tests for access control and workflow; use postgres for production validation.
"""
import os
import sys
import tempfile
import types
from pathlib import Path


def main():
    work = Path(tempfile.mkdtemp(prefix="heimanbo_v15_"))
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{work/'test.sqlite3'}",
        "JWT_SECRET": "v"*64,
        "ADMIN_EMAIL": "root@example.com",
        "ADMIN_PASSWORD": "test-only-secret-password-123",
        "VIDEO_DIR": str(work/"videos"),
        "SITE_ORIGIN": "http://localhost:8080",
        "COOKIE_SECURE": "false",
    })
    for key in ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]:
        os.environ.pop(key, None)
    try:
        import pwdlib
    except ModuleNotFoundError:
        fake = types.ModuleType("pwdlib")
        class FakeHash:
            @classmethod
            def recommended(cls): return cls()
            def hash(self, s): return "test-hash:"+s
            def verify(self, p, h): return h=="test-hash:"+p
        fake.PasswordHash = FakeHash
        sys.modules['pwdlib'] = fake

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from app.main import (app, Base, engine, SessionLocal, User, Merchant, MerchantAccount,
                          BusinessOrder, Video, current_user)
    from app.publish_tasks_v14 import PublishReviewEvent, PublishTask

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        staff = User(email="staff@local.test", name="staff", role="admin", password_hash="hash")
        merchant_a = User(email="a@local.test", name="a", role="merchant", password_hash="hash")
        merchant_b = User(email="b@local.test", name="b", role="merchant", password_hash="hash")
        db.add_all([staff, merchant_a, merchant_b]); db.flush()
        ma = Merchant(name="商家甲",status="approved")
        mb = Merchant(name="商家乙",status="approved")
        db.add_all([ma,mb]); db.flush()
        db.add_all([MerchantAccount(merchant_id=ma.id,user_id=merchant_a.id),
                    MerchantAccount(merchant_id=mb.id,user_id=merchant_b.id)])
        db.commit()
        staff_id, a_id, b_id=staff.id,merchant_a.id,merchant_b.id
    (work/"videos").mkdir(exist_ok=True)

    client=TestClient(app)
    def assume(uid):
        def auth():
            with SessionLocal() as db:
                user=db.get(User, uid)
                db.expunge(user)
                return user
        app.dependency_overrides[current_user]=auth
    def assert_status(expected, method, path, **kwargs):
        r=client.request(method,path,**kwargs)
        assert r.status_code==expected, (method,path,expected,r.status_code,r.text[:1000])
        print("PASS", method, path, expected)
        return r.json() if r.headers.get('content-type','').startswith('application/json') else r

    with client:
        # Only merchant may initiate orders. Staff can accept and quote.
        assume(staff_id)
        assert_status(403, 'POST', '/api/orders', json={
            'client_name':'internal', 'title':'manual order', 'amount':'100',
            'order_date':'2026-10-31', 'service_type':'拍摄+制作+剪辑'
        })
        assert_status(403, 'POST', '/api/staff/publish-tasks', json={
            'order_id':1, 'title':'staff should not create'
        })
        assume(a_id)
        req=assert_status(201,'POST','/api/portal/project-requests',json={
            'title':'商家甲新品拍摄和剪辑', 'brief':'制作10条TikTok产品视频，保留真实质感',
            'video_count':10,'aspect_ratio':'9:16','duration_seconds':15
        })
        req_id=req['id']
        assert req['status']=='pending'
        assume(b_id)
        assert_status(404, 'POST', '/api/portal/publish-tasks', json={
            'order_id':123456, 'title':'试图关联别人的订单'
        })
        assert_status(403, 'GET', '/api/orders')
        assume(staff_id)
        converted=assert_status(201,'POST',f'/api/staff/project-requests/{req_id}/convert',json={
            'amount':'5000.00','cost':'900.00', 'staff_note':'已确认拍摄数量与价格'
        })
        order_id=converted['order_id']
        with SessionLocal() as db:
            order=db.get(BusinessOrder,order_id)
            assert order and order.merchant_id is not None
            assert order.amount_cents==500000
        assume(b_id)
        assert_status(404,'POST','/api/portal/publish-tasks',json={
            'order_id':order_id, 'title':'试图建立其他商家发布任务'
        })
        assume(a_id)
        my_orders=assert_status(200,'GET','/api/portal/orders')
        assert len(my_orders)==1 and my_orders[0]['id']==order_id
        task=assert_status(201,'POST','/api/portal/publish-tasks',json={
            'order_id':order_id, 'title':'新品视频10条发布任务', 'platform':'TikTok',
            'instructions':'请重点展示产品功能，不要虚假宣传'
        })
        task_id=task['id']
        assert task['status']=='draft'
        tasks=assert_status(200,'GET','/api/portal/publish-tasks')
        assert len(tasks)==1 and tasks[0]['id']==task_id
        assert_status(409,'POST',f'/api/portal/publish-tasks/{task_id}/published',json={})
        assume(b_id)
        assert_status(404,'GET',f'/api/portal/publish-tasks/{task_id}')
        assert_status(404,'POST',f'/api/portal/publish-tasks/{task_id}/published',json={})
        assert_status(200,'GET','/api/portal/publish-tasks')
        assume(staff_id)
        vid=Video(id='demo-15', filename='product.mp4', storage_key='product.mp4',
                  mime='video/mp4',size_bytes=32,status='ready', created_by=staff_id)
        with SessionLocal() as db: db.add(vid); db.commit()
        (work/'videos'/'product.mp4').write_bytes(b'\x00\x00\x00\x18ftypisom' + b'0'*24)
        linked=assert_status(201,'POST',f'/api/staff/publish-tasks/{task_id}/videos',json={'video_id':'demo-15'})
        assert linked['status']=='pending_review'
        link_id=linked['videos'][0]['id']
        assert_status(403,'POST',f'/api/staff/publish-tasks/{task_id}/published',json={})
        assume(b_id)
        assert_status(404,'GET',f'/api/portal/publish-tasks/{task_id}/videos/{link_id}/stream')
        assert_status(404,'POST',f'/api/portal/publish-tasks/{task_id}/videos/{link_id}/review',json={'decision':'approved'})
        assume(a_id)
        approved=assert_status(200,'POST',f'/api/portal/publish-tasks/{task_id}/videos/{link_id}/review',json={'decision':'approved'})
        assert approved['status']=='approved'
        published=assert_status(200,'POST',f'/api/portal/publish-tasks/{task_id}/published',json={
            'published_url':'https://www.tiktok.com/@example/video/100'
        })
        assert published['status']=='published'
        assert_status(409,'POST',f'/api/portal/publish-tasks/{task_id}/published',json={})
        with SessionLocal() as db:
            assert len(db.scalars(select(PublishReviewEvent)).all())==1
            assert db.get(PublishTask,task_id).merchant_id == db.get(BusinessOrder,order_id).merchant_id

    print('All merchant order and publishing tests passed.')

if __name__=='__main__': main()
