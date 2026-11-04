"""V2.1.2: three-domain role isolation and administrator control surface."""
import os,sys,tempfile,types
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
work=Path(tempfile.mkdtemp(prefix='heimanbo_v212_domains_'))
os.environ.update({
  'DATABASE_URL':f'sqlite:///{work / "site.sqlite3"}',
  'JWT_SECRET':'k'*64,
  'ADMIN_EMAIL':'root@example.com',
  'ADMIN_PASSWORD':'some-admin-password-123456',
  'VIDEO_DIR':str(work/'videos'),
  'SITE_ORIGIN':'https://test-v2.heimanbo.com',
  'COOKIE_SECURE':'false', 'COOKIE_DOMAIN':'',
  'APP_ENV':'development', 'OTP_DEBUG':'false',
  'PUBLIC_APP_URL':'https://test-v2.heimanbo.com'
})
try:
 import pwdlib
except ModuleNotFoundError:
 fake=types.ModuleType('pwdlib')
 class FakeHash:
  @classmethod
  def recommended(cls):return cls()
  def hash(self,s):return 'test-hash:'+s
  def verify(self,p,h):return h=='test-hash:'+p
 fake.PasswordHash=FakeHash
 sys.modules['pwdlib']=fake
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.main import app, Base, engine, SessionLocal, User, Merchant, MerchantAccount, PASSWORD
Base.metadata.create_all(engine)
with SessionLocal() as db:
  merch=Merchant(name='Domain Merchant',status='approved')
  db.add(merch);db.flush()
  for email,role in [('admin@example.com','admin'),('producer@example.com','producer'),('merchant@example.com','merchant')]:
    u=User(name=role,email=email,role=role,password_hash=PASSWORD.hash('password-1234567890'))
    db.add(u);db.flush()
    if role=='merchant':db.add(MerchantAccount(merchant_id=merch.id,user_id=u.id))
  db.commit()

def login(base_url,role):
  client=TestClient(app,base_url=base_url)
  r=client.post('/api/auth/login',json={'email':f'{role}@example.com','password':'password-1234567890'})
  assert r.status_code==200, r.text
  return client

admin=login('https://heimanbo.com','admin')
assert admin.get('/api/auth/me').status_code==200
assert admin.get('/api/system/overview').status_code==200
assert admin.get('/api/users').status_code==200
assert admin.get('/api/merchants').status_code==200
merchant_admin_host=login('https://heimanbo.com','merchant')
assert merchant_admin_host.get('/api/auth/me').status_code==403
producer_admin_host=login('https://heimanbo.com','producer')
assert producer_admin_host.get('/api/auth/me').status_code==403
producer=login('https://video.heimanbo.com','producer')
assert producer.get('/api/auth/me').status_code==200
assert producer.get('/api/staff/publish-tasks').status_code==200
assert producer.get('/api/users').status_code==403
merchant_video_host=login('https://video.heimanbo.com','merchant')
assert merchant_video_host.get('/api/auth/me').status_code==403
merchant_delivery=login('https://deliver.heimanbo.com','merchant')
assert merchant_delivery.get('/api/auth/me').status_code==200
assert merchant_delivery.get('/api/portal/orders').status_code==200
assert merchant_delivery.get('/api/merchants').status_code==403
producer_delivery=login('https://deliver.heimanbo.com','producer')
assert producer_delivery.get('/api/auth/me').status_code==200
assert producer_delivery.get('/api/staff/publish-tasks').status_code==200
admin_delivery=login('https://deliver.heimanbo.com','admin')
assert admin_delivery.get('/api/auth/me').status_code==200
assert admin_delivery.get('/api/users').status_code==200
print('PASS V2.1.2 domain authorization, admin management, merchant isolation')
