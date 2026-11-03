"""Simulate a V2.0 database and verify V2.1 adds task assignment columns without losing rows."""
import os, sys, tempfile, types
from pathlib import Path

work=Path(tempfile.mkdtemp(prefix="heimanbo_v21_migration_"))
os.environ.update({
 "DATABASE_URL":f"sqlite:///{work/'test.sqlite3'}","JWT_SECRET":"m"*64,
 "ADMIN_EMAIL":"root@example.com","ADMIN_PASSWORD":"test-only-admin-password-123",
 "VIDEO_DIR":str(work/"videos"),"SITE_ORIGIN":"http://localhost:8080",
 "COOKIE_SECURE":"false","COOKIE_DOMAIN":"","APP_ENV":"development","OTP_DEBUG":"false",
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
from datetime import date
from sqlalchemy import inspect, select, text, func
from app.main import Base, engine, SessionLocal, User, Merchant, BusinessOrder, apply_v21_migrations
from app.publish_tasks_v14 import PublishTask
Base.metadata.create_all(engine)
with SessionLocal() as db:
    admin=User(email="admin@example.com",name="Admin",role="admin",password_hash="test-hash:admin-password-12345")
    merchant=Merchant(name="Existing Merchant",status="pending")
    rejected=Merchant(name="Previously Rejected",status="rejected")
    db.add_all([admin,merchant,rejected]);db.flush()
    order=BusinessOrder(order_no="BM-OLD-1",client_name=merchant.name,merchant_id=merchant.id,contact="",title="Old order",
        service_type="制作",owner_id=admin.id,amount_cents=5000,cost_cents=0,status="confirmed",order_date=date.today(),created_by=admin.id)
    db.add(order);db.flush()
    task=PublishTask(order_id=order.id,merchant_id=merchant.id,title="Existing task",platform="TikTok",created_by=admin.id)
    db.add(task);db.commit();task_id=task.id;merchant_id=merchant.id;rejected_id=rejected.id
# Emulate the existing V2.0 table by removing only the new V2.1 columns.
with engine.begin() as conn:
    # SQLite cannot DROP a column that participates in a foreign key, so rebuild only
    # this test fixture table to represent the older V2.0 schema (the production
    # migration never rebuilds this table).
    conn.execute(text("CREATE TABLE publish_tasks_v14_legacy (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, merchant_id INTEGER NOT NULL, title VARCHAR(200) NOT NULL, platform VARCHAR(40) NOT NULL, account_label VARCHAR(120) NOT NULL, publish_date DATE, instructions TEXT NOT NULL, status VARCHAR(32) NOT NULL, published_url VARCHAR(500) NOT NULL, created_by INTEGER NOT NULL, created_at DATETIME, updated_at DATETIME)"))
    conn.execute(text("INSERT INTO publish_tasks_v14_legacy (id,order_id,merchant_id,title,platform,account_label,publish_date,instructions,status,published_url,created_by,created_at,updated_at) SELECT id,order_id,merchant_id,title,platform,account_label,publish_date,instructions,status,published_url,created_by,created_at,updated_at FROM publish_tasks_v14"))
    conn.execute(text("DROP TABLE publish_tasks_v14"))
    conn.execute(text("ALTER TABLE publish_tasks_v14_legacy RENAME TO publish_tasks_v14"))
apply_v21_migrations()
cols={c["name"] for c in inspect(engine).get_columns("publish_tasks_v14")}
assert {"assigned_user_id","assigned_at","accepted_at"}.issubset(cols),cols
with SessionLocal() as db:
    assert db.scalar(select(func.count(PublishTask.id)))==1
    old=db.get(PublishTask,task_id)
    assert old and old.title=="Existing task" and old.assigned_user_id is None
    assert db.get(Merchant,merchant_id).status=="approved"
    assert db.get(Merchant,rejected_id).status=="rejected"
print("PASS V2.1 additive schema migration preserves existing task and merchant records")
