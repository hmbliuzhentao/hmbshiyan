"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

type Panel = "auth" | "work" | "video" | "merchant" | "system";
type User = { id:number; name:string; email:string; phone?:string; role:string; is_active:boolean };
type Item = { id:number; title:string; body:string; status:string; merchant_id:number|null; metadata:Record<string,unknown>; created_at:string };
type DataResponse = { items?:Item[]; total?:number; [key:string]:unknown };

const PANEL_META: Record<Panel,{title:string;subtitle:string;domain:string}> = {
  auth:{title:"黑曼波账号中心",subtitle:"统一身份认证与账号安全",domain:"auth.heimanbo.com"},
  work:{title:"内部管理中心",subtitle:"商家、订单、团队与经营数据",domain:"work.heimanbo.com"},
  video:{title:"视频制作中心",subtitle:"脚本、分镜、素材与成片任务",domain:"video.heimanbo.com"},
  merchant:{title:"商家审核工作台",subtitle:"只展示当前商家的订单与视频",domain:"merchant.heimanbo.com"},
  system:{title:"系统管理中心",subtitle:"账号、权限、安全、域名与审计",domain:"system.heimanbo.com"},
};

const NAV: Record<Exclude<Panel,"auth">,{group:string;items:{id:string;label:string;kind?:string;endpoint?:string}[]}[]> = {
  work:[
    {group:"运营总览",items:[{id:"overview",label:"数据总览",endpoint:"/dashboard"}]},
    {group:"业务管理",items:[{id:"orders",label:"订单台账",endpoint:"/orders"},{id:"merchants",label:"商家管理",endpoint:"/merchants"},{id:"products",label:"产品中心",kind:"product"}]},
    {group:"团队协作",items:[{id:"tasks",label:"任务进度",endpoint:"/staff/publish-tasks"},{id:"team",label:"团队资料",kind:"note"}]},
    {group:"经营分析",items:[{id:"analytics",label:"数据统计",endpoint:"/dashboard"},{id:"account",label:"账号安全",endpoint:"/auth/identities"}]},
  ],
  video:[
    {group:"制作任务",items:[{id:"tasks",label:"视频任务",endpoint:"/staff/publish-tasks"},{id:"videos",label:"视频素材库",endpoint:"/videos"}]},
    {group:"创作工具",items:[{id:"scripts",label:"脚本中心",kind:"script"},{id:"storyboards",label:"分镜中心",kind:"storyboard"},{id:"prompts",label:"提示词库",kind:"prompt"}]},
    {group:"素材管理",items:[{id:"products",label:"产品资料",kind:"product"},{id:"assets",label:"图片与素材",kind:"asset"},{id:"account",label:"账号安全",endpoint:"/auth/identities"}]},
  ],
  merchant:[
    {group:"商家工作台",items:[{id:"my-orders",label:"我的合作订单",endpoint:"/portal/orders"},{id:"my-videos",label:"视频审核",endpoint:"/portal/publish-tasks"},{id:"products",label:"我的产品",kind:"product"},{id:"profile",label:"合作资料",endpoint:"/portal/me"},{id:"account",label:"账号安全",endpoint:"/auth/identities"}]},
  ],
  system:[
    {group:"系统安全",items:[{id:"overview",label:"系统总览",endpoint:"/system/overview"},{id:"users",label:"用户与账号",endpoint:"/users"},{id:"audit",label:"操作审计",endpoint:"/system/audit-logs"},{id:"sessions",label:"登录会话",endpoint:"/auth/sessions"},{id:"account",label:"账号安全",endpoint:"/auth/identities"}]},
    {group:"平台配置",items:[{id:"domains",label:"域名管理",kind:"note"},{id:"storage",label:"存储配置",kind:"note"},{id:"security",label:"安全设置",kind:"note"}]},
  ],
};

function detectPanel(host:string):Panel {
  if(host.startsWith("auth.")) return "auth";
  if(host.startsWith("merchant.")) return "merchant";
  if(host.startsWith("video.")) return "video";
  if(host.startsWith("system.")) return "system";
  return "work";
}
function homeForRole(role:string) {
  if(role==="merchant") return "https://merchant.heimanbo.com";
  if(role==="super_admin" || role==="admin" || role==="manager" || role==="viewer") return "https://work.heimanbo.com";
  return "https://video.heimanbo.com";
}
async function api<T=any>(path:string, init?:RequestInit):Promise<T> {
  const res=await fetch(`/api${path}`,{credentials:"include",...init});
  if(!res.ok) {
    const body=await res.json().catch(()=>({}));
    throw new Error(body.detail || `请求失败 (${res.status})`);
  }
  if(res.status===204) return undefined as T;
  return res.json();
}
function toItems(value:any):Item[] {
  if(Array.isArray(value)) return value;
  if(value && Array.isArray(value.items)) return value.items;
  return [];
}

export default function Home() {
  const [panel,setPanel]=useState<Panel>("work");
  const [user,setUser]=useState<User|null>(null);
  const [checked,setChecked]=useState(false);
  const [section,setSection]=useState("overview");
  const [data,setData]=useState<any>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [identifier,setIdentifier]=useState("");
  const [password,setPassword]=useState("");
  const [showRegister,setShowRegister]=useState(false);
  const [showReset,setShowReset]=useState(false);
  const [reg,setReg]=useState({name:"",merchant_name:"",destination:"",code:"",password:""});
  const [reset,setReset]=useState({destination:"",code:"",new_password:""});
  const [otpBusy,setOtpBusy]=useState(false);
  const [providers,setProviders]=useState({wechat:false,email_otp:false,sms_otp:false});
  const [newItem,setNewItem]=useState({title:"",body:"",status:"draft"});
  const [showCreate,setShowCreate]=useState(false);
  const [bindForm,setBindForm]=useState({destination:"",code:""});
  const [passwordForm,setPasswordForm]=useState({current_password:"",new_password:""});

  useEffect(()=>{
    const p=detectPanel(window.location.hostname);
    setPanel(p);
    setSection(p==="merchant"?"my-orders":p==="video"?"tasks":"overview");
    api("/auth/providers").then(setProviders).catch(()=>{});
    api<User>("/auth/me").then(setUser).catch(()=>{}).finally(()=>setChecked(true));
  },[]);

  useEffect(()=>{
    if(checked && user && panel==="auth") window.location.href=homeForRole(user.role);
  },[checked,user,panel]);

  const groups=useMemo(()=>panel==="auth"?[]:NAV[panel],[panel]);
  const selected=groups.flatMap(g=>g.items).find(i=>i.id===section);

  const load=useCallback(async()=>{
    if(!user || !selected) return;
    setLoading(true);setError("");
    try {
      if(selected.kind) {
        const result=await api(`/workspace/${selected.kind}`);
        setData(result);
      } else if(selected.endpoint) {
        const result=await api(selected.endpoint);
        setData(result);
      } else setData(null);
    } catch(e) { setError((e as Error).message);setData(null); }
    finally { setLoading(false); }
  },[user,selected]);
  useEffect(()=>{load();},[load]);

  function roleAllowed():boolean {
    if(!user) return false;
    if(panel==="merchant") return user.role==="merchant";
    if(panel==="system") return ["super_admin","admin"].includes(user.role);
    if(panel==="video") return ["super_admin","admin","manager","producer","editor","viewer"].includes(user.role);
    if(panel==="work") return ["super_admin","admin","manager","viewer"].includes(user.role);
    return true;
  }
  async function login(e:FormEvent) {
    e.preventDefault();setLoading(true);setError("");
    try {
      const u=await api<User>("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({identifier,password})});
      setUser(u);
      const destination=homeForRole(u.role);
      if(panel==="auth" || !destination.includes(window.location.hostname)) window.location.href=destination;
      else {setPanel(detectPanel(window.location.hostname));setSection("overview");}
    } catch(e) {setError((e as Error).message);}
    finally {setLoading(false);}
  }
  async function sendOtp(destination:string,purpose:"register"|"password_reset"|"bind") {
    if(!destination.trim()) {setError("请先填写手机号或邮箱");return;}
    setOtpBusy(true);setError("");setNotice("");
    try { await api("/auth/otp/request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({destination,purpose})});setNotice("验证码已发送，请检查短信或邮箱。");}
    catch(e){setError((e as Error).message);}
    finally{setOtpBusy(false);}
  }
  async function register(e:FormEvent) {
    e.preventDefault();setLoading(true);setError("");
    try {
      const result=await api<{user:User;merchant_status:string}>("/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(reg)});
      setUser(result.user);setNotice("注册成功，商家资料等待管理员审核。");
      window.location.href="https://merchant.heimanbo.com";
    } catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }
  async function resetPassword(e:FormEvent) {
    e.preventDefault();setLoading(true);setError("");
    try {await api("/auth/password/reset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(reset)});setNotice("密码已重置，请使用新密码登录。");setShowReset(false);}
    catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }
  async function bindContact(e:FormEvent) {
    e.preventDefault();setLoading(true);setError("");
    try {await api("/auth/contact/bind",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(bindForm)});setNotice("联系方式绑定成功。");setBindForm({destination:"",code:""});await load();}
    catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }
  async function savePassword(e:FormEvent) {
    e.preventDefault();setLoading(true);setError("");
    try {
      if(data?.has_password) await api("/auth/password/change",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(passwordForm)});
      else await api("/auth/password/set",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({new_password:passwordForm.new_password})});
      setNotice("密码更新成功。");setPasswordForm({current_password:"",new_password:""});await load();
    } catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }
  async function revokeSession(id:number) {
    setLoading(true);setError("");
    try {await api(`/auth/sessions/${id}`,{method:"DELETE"});await load();setNotice("登录会话已撤销。");}
    catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }
  async function logout() {
    try{await api("/auth/logout",{method:"POST"});}catch{}
    setUser(null);window.location.href="https://auth.heimanbo.com";
  }
  async function createItem(e:FormEvent) {
    e.preventDefault();if(!selected?.kind)return;
    setLoading(true);setError("");
    try {await api(`/workspace/${selected.kind}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(newItem)});setNewItem({title:"",body:"",status:"draft"});setShowCreate(false);await load();setNotice("保存成功。");}
    catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  }

  if(!checked) return <main className="boot"><div className="spinner"/>正在连接黑曼波工作台…</main>;

  if(!user || panel==="auth") return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand"><img src="/brand-logo.png" alt="黑曼波 Logo"/><div><b>黑曼波工作台</b><small>BLACK MAMBA · VIDEO OPERATIONS</small></div></div>
        <div className="auth-tabs"><button className={!showRegister&&!showReset?"active":""} onClick={()=>{setShowRegister(false);setShowReset(false);}}>账号登录</button><button className={showRegister?"active":""} onClick={()=>{setShowRegister(true);setShowReset(false);}}>商家注册</button></div>
        {showRegister ? <form onSubmit={register} className="form">
          <label>联系人姓名<input required value={reg.name} onChange={e=>setReg({...reg,name:e.target.value})}/></label>
          <label>商家名称<input value={reg.merchant_name} onChange={e=>setReg({...reg,merchant_name:e.target.value})} placeholder="公司或店铺名称"/></label>
          <label>手机号或邮箱<input required value={reg.destination} onChange={e=>setReg({...reg,destination:e.target.value})}/></label>
          <div className="otp-row"><input required value={reg.code} onChange={e=>setReg({...reg,code:e.target.value})} placeholder="验证码"/><button type="button" disabled={otpBusy} onClick={()=>sendOtp(reg.destination,"register")}>{otpBusy?"发送中":"获取验证码"}</button></div>
          <label>登录密码<input required minLength={12} type="password" value={reg.password} onChange={e=>setReg({...reg,password:e.target.value})} placeholder="至少 12 位"/></label>
          <button className="primary" disabled={loading}>提交注册申请</button>
        </form> : showReset ? <form onSubmit={resetPassword} className="form">
          <label>手机号或邮箱<input required value={reset.destination} onChange={e=>setReset({...reset,destination:e.target.value})}/></label>
          <div className="otp-row"><input required value={reset.code} onChange={e=>setReset({...reset,code:e.target.value})} placeholder="验证码"/><button type="button" disabled={otpBusy} onClick={()=>sendOtp(reset.destination,"password_reset")}>获取验证码</button></div>
          <label>新密码<input required minLength={12} type="password" value={reset.new_password} onChange={e=>setReset({...reset,new_password:e.target.value})}/></label>
          <button className="primary" disabled={loading}>重置密码</button><button type="button" className="link-button" onClick={()=>setShowReset(false)}>返回登录</button>
        </form> : <form onSubmit={login} className="form">
          <label>手机号 / 邮箱<input required autoComplete="username" value={identifier} onChange={e=>setIdentifier(e.target.value)} placeholder="请输入手机号或邮箱"/></label>
          <label>登录密码<input required autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="请输入密码"/></label>
          <button className="primary" disabled={loading}>{loading?"登录中…":"登录工作台"}</button>
          <button type="button" className="link-button" onClick={()=>setShowReset(true)}>忘记密码？</button>
          {providers.wechat && <a className="wechat-button" href="/api/auth/wechat/start">微信扫码登录</a>}
        </form>}
        {error&&<p className="error">{error}</p>}{notice&&<p className="notice">{notice}</p>}
        <p className="auth-foot">商家账号需审核通过后访问订单和视频。员工账号由管理员邀请。</p>
      </section>
    </main>
  );

  if(!roleAllowed()) return <main className="boot"><section className="denied"><h1>无权访问此面板</h1><p>当前账号角色：{user.role}。此域名仅对指定角色开放。</p><button onClick={logout}>退出并切换账号</button></section></main>;

  const records=toItems(data);
  const isWorkspace=Boolean(selected?.kind);
  return <main className="app-shell">
    <aside className="sidebar">
      <div className="brand side-brand"><img src="/brand-logo.png" alt="黑曼波 Logo"/><div><b>黑曼波</b><small>V2.0 WORKSPACE</small></div></div>
      <div className="panel-chip"><span className="dot"/>{PANEL_META[panel].title}</div>
      <nav>{groups.map(group=><div className="nav-group" key={group.group}><small>{group.group}</small>{group.items.map(item=><button key={item.id} className={section===item.id?"nav-item active":"nav-item"} onClick={()=>{setSection(item.id);setData(null);}}><span className="nav-icon">◈</span>{item.label}</button>)}</div>)}</nav>
      <div className="side-bottom"><div className="user-mini"><div className="avatar">{user.name.slice(0,1)}</div><div><b>{user.name}</b><small>{user.role}</small></div></div><button className="logout" onClick={logout}>退出登录</button></div>
    </aside>
    <section className="main-area">
      <header className="topbar"><div><span className="eyebrow">{PANEL_META[panel].domain}</span><h1>{selected?.label || PANEL_META[panel].title}</h1><p>{PANEL_META[panel].subtitle}</p></div><div className="top-actions"><span className="status-pill">系统在线</span><button onClick={()=>load()}>刷新</button><a href="https://auth.heimanbo.com">账号中心</a></div></header>
      {error&&<div className="alert error">{error}</div>}{notice&&<div className="alert notice">{notice}</div>}
      <div className="content">
        {section==="overview" && <div className="overview-grid">
          <div className="welcome card"><span className="eyebrow">WELCOME BACK</span><h2>你好，{user.name}</h2><p>这里是{PANEL_META[panel].title}。请选择左侧功能开始工作。</p><div className="quick-links">{groups.flatMap(g=>g.items).slice(0,4).map(x=><button key={x.id} onClick={()=>setSection(x.id)}>{x.label} →</button>)}</div></div>
          <div className="metric card"><small>当前面板</small><strong>{panel.toUpperCase()}</strong><span>{PANEL_META[panel].domain}</span></div>
          <div className="metric card"><small>账号角色</small><strong>{user.role}</strong><span>服务端权限验证已启用</span></div>
          <div className="metric card"><small>认证方式</small><strong>多因素就绪</strong><span>手机号 / 邮箱 / 微信（需配置服务商）</span></div>
          <div className="card wide"><h3>V2.0 功能分区</h3><div className="feature-grid">{groups.flatMap(g=>g.items).map(x=><button key={x.id} onClick={()=>setSection(x.id)}><b>{x.label}</b><span>打开功能 →</span></button>)}</div></div>
          {panel==="system"&&<div className="card wide"><h3>系统状态</h3><pre>{JSON.stringify(data||{},null,2)}</pre></div>}
        </div>}
        {section!=="overview" && <div className="card data-card">
          <div className="section-head"><div><span className="eyebrow">{panel.toUpperCase()} / MODULE</span><h2>{selected?.label}</h2><p>按当前账号权限和数据归属加载。</p></div>{isWorkspace&&<button className="primary compact" onClick={()=>setShowCreate(!showCreate)}>＋ 新建</button>}</div>
          {showCreate&&isWorkspace&&<form className="create-form" onSubmit={createItem}><label>名称<input required value={newItem.title} onChange={e=>setNewItem({...newItem,title:e.target.value})}/></label><label>说明<textarea value={newItem.body} onChange={e=>setNewItem({...newItem,body:e.target.value})}/></label><label>状态<select value={newItem.status} onChange={e=>setNewItem({...newItem,status:e.target.value})}><option value="draft">草稿</option><option value="active">进行中</option><option value="archived">归档</option></select></label><button className="primary" disabled={loading}>保存</button></form>}
          {section==="account" && data && <div className="account-grid">
            <div className="account-panel"><h3>登录方式与绑定</h3><div className="identity-row"><span>邮箱</span><b>{data.email||"未绑定"}</b></div><div className="identity-row"><span>手机号</span><b>{data.phone||"未绑定"}</b></div><div className="identity-row"><span>微信</span><b>{data.wechat_bound?"已绑定":"未绑定"}</b></div>
              <form className="form compact-form" onSubmit={bindContact}><label>绑定手机号或邮箱<input required value={bindForm.destination} onChange={e=>setBindForm({...bindForm,destination:e.target.value})}/></label><div className="otp-row"><input required value={bindForm.code} onChange={e=>setBindForm({...bindForm,code:e.target.value})} placeholder="验证码"/><button type="button" disabled={otpBusy} onClick={()=>sendOtp(bindForm.destination,"bind")}>获取验证码</button></div><button className="primary" disabled={loading}>验证并绑定</button></form>
              {providers.wechat && <a className="wechat-button" href="/api/auth/wechat/start?mode=bind">绑定微信账号</a>}
            </div>
            <div className="account-panel"><h3>密码安全</h3><p className="subtle">{data.has_password?"已设置密码，可定期修改。":"微信账号尚未设置独立密码，请先绑定并验证手机号或邮箱。"}</p><form className="form compact-form" onSubmit={savePassword}>{data.has_password&&<label>当前密码<input type="password" required value={passwordForm.current_password} onChange={e=>setPasswordForm({...passwordForm,current_password:e.target.value})}/></label>}<label>新密码<input type="password" minLength={12} required value={passwordForm.new_password} onChange={e=>setPasswordForm({...passwordForm,new_password:e.target.value})}/></label><button className="primary" disabled={loading}>{data.has_password?"修改密码":"设置密码"}</button></form></div>
          </div>}
          {section==="sessions" && <div className="record-list">{records.map((s:any)=><article className="record" key={s.id}><div><b>{s.current?"当前设备":`登录设备 #${s.id}`}</b><small>{s.ip} · {s.created_at} · {s.revoked?"已撤销":s.user_agent}</small></div>{!s.revoked&&<button className="link-button" onClick={()=>revokeSession(s.id)}>撤销</button>}</article>)}</div>}
          {section!=="account" && section!=="sessions" && (loading?<div className="empty">正在加载…</div>:data===null?<div className="empty">暂无数据或接口尚未返回结果。</div>:records.length>0?<div className="record-list">{records.map((item:any,i:number)=><article className="record" key={item.id??i}><div><b>{item.title||item.order_no||item.filename||item.name||`记录 ${i+1}`}</b><small>{item.status||item.role||item.created_at||""}</small>{item.body&&<p>{item.body}</p>}</div><span className="record-id">#{item.id??i+1}</span></article>)}</div>:<pre className="json-view">{JSON.stringify(data,null,2)}</pre>)}
          <div className="module-footer"><a href="/legacy-v15">打开 V1.5 完整业务页面</a><span>V2.0 · 数据权限由后端校验</span></div>
        </div>}
      </div>
    </section>
  </main>;
}
