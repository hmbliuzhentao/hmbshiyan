"use client";
import "./legacy.css";
import { useEffect, useState, type FormEvent } from "react";
import OrdersPanel, { OrdersSummary } from "../orders";
import {MerchantsPanelV14, MerchantPortalV14} from "../merchants-v14";
import {StaffPublishTasksV14} from "../publish-tasks-v14";
import {StaffProjectsV13} from "../merchant-projects-v13";
import {AdminOperations} from "../admin-operations";

type User = { id: number; name: string; email: string|null; role: string; is_active:boolean; created_at: string };
type Video = { id: string; filename: string; size_bytes: number; status: string; created_at: string; stream_url: string; created_by: number };
type Task = { id: number; type: string; status: string; detail: string; created_at: string };
type Section = "dashboard" | "merchants" | "orders" | "publish" | "videos" | "upload" | "tasks" | "users" | "client_projects" | "system";
type NavGroup = {title:string; items:{id:Section;label:string;adminOnly?:boolean}[]};
// Keep the top-level navigation short. Upload and activity history stay accessible
// from Video Management, without adding two more permanent sidebar items.
const navGroups:NavGroup[]=[
  {title:"业务管理",items:[
    {id:"dashboard",label:"管理总览",adminOnly:true},
    {id:"orders",label:"订单管理",adminOnly:true},
    {id:"publish",label:"任务与交付"},
    {id:"videos",label:"视频管理",adminOnly:true},
  ]},
  {title:"人员与系统",items:[
    {id:"merchants",label:"商家管理",adminOnly:true},
    {id:"users",label:"账号权限",adminOnly:true},
    {id:"system",label:"操作记录",adminOnly:true},
  ]},
];
// A single backend serves three role-aware surfaces. The test domain retains
// the full legacy role-aware view until production DNS/TLS is configured.
type SiteMode = "admin" | "video" | "deliver" | "test";
function siteMode(host: string, search = ""): SiteMode {
  // Both www (primary domain) and test-v2 serve all three workspaces.
  // Server-side API permissions still enforce admin/staff/merchant roles.
  if (host === "www.heimanbo.com" || host === "test-v2.heimanbo.com") {
    const view = new URLSearchParams(search).get("workspace");
    if (view === "admin" || view === "video" || view === "deliver") return view;
    return host === "www.heimanbo.com" ? "admin" : "test";
  }
  if (host === "heimanbo.com" || host === "work.heimanbo.com") return "admin";
  if (host === "video.heimanbo.com") return "video";
  if (host === "deliver.heimanbo.com") return "deliver";
  return "test";
}
// Canonical domain: one HTTPS host, three role-specific workspaces.
const domainLinks = {
  admin: "https://www.heimanbo.com/?workspace=admin",
  video: "https://www.heimanbo.com/?workspace=video",
  deliver: "https://www.heimanbo.com/?workspace=deliver",
};
const menu=navGroups.flatMap(g=>g.items);
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: "include", ...options });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `请求失败：${res.status}`);
  }
  return res.json();
}
const bytes = (n: number) => n >= 1024**3 ? (n/1024**3).toFixed(2)+" GB" : n >= 1024**2 ? (n/1024**2).toFixed(2)+" MB" : (n/1024).toFixed(1)+" KB";
const day = (date: string) => date ? new Date(date).toLocaleString("zh-CN") : "—";

export default function Home() {
  const [user, setUser] = useState<User|null>(null);
  const [checked, setChecked] = useState(false);
  const [site, setSite] = useState<SiteMode>("test");
  const [sameHost, setSameHost] = useState(false);
  const workspaceHref = (target: "admin" | "video" | "deliver") =>
    sameHost ? `/?workspace=${target}` : domainLinks[target];
  const [systemEvents, setSystemEvents] = useState<{id:number;action:string;target_type:string;target_id:string;created_at:string;actor_id:number}[]>([]);
  const [section, setSection] = useState<Section>("dashboard");
  const [orderTab,setOrderTab] = useState<"ledger"|"requests">("ledger");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [videos, setVideos] = useState<Video[]>([]);
  const [totalVideos, setTotalVideos] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [uploadFile, setUploadFile] = useState<File|null>(null);
  const [uploadToTask,setUploadToTask]=useState("");
  const [publishChoices,setPublishChoices]=useState<{id:number;title:string;order_no:string;status:string}[]>([]);
  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "producer", merchant_name: "" });
  const [wechatReady, setWechatReady] = useState(false);
  const [activeVideo, setActiveVideo] = useState<Video|null>(null);

  useEffect(() => {
    const host = window.location.hostname;
    const initialSite = siteMode(host, window.location.search);
    setSameHost(host === "www.heimanbo.com" || host === "test-v2.heimanbo.com");
    setSite(initialSite);
    api<User>("/auth/me").then(u => {
      setUser(u);
      setSection(u.role === "producer" || initialSite === "video" ? "publish" : initialSite === "deliver" ? "upload" : "dashboard");
    }).catch(() => {}).finally(() => setChecked(true));
    api<{wechat:boolean}>("/auth/providers").then(p => setWechatReady(!!p.wechat)).catch(() => setWechatReady(false));
  }, []);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("error");
    const messages:Record<string,string>={
      wechat_authorization_failed:"微信授权失败或二维码已过期，请重新扫码。",
      wechat_already_bound:"该微信已绑定其他账号。",
      wechat_identity_already_bound:"当前账号已经绑定了另一个微信。",
      account_disabled:"账号已停用，请联系管理员。",
      login_required:"登录状态已失效，请重新登录后绑定微信。",
      wechat_state_mismatch:"微信绑定状态不匹配，请重新操作。",
    };
    if(code)setError(messages[code]||"微信授权未完成，请重试。");
    if(params.get("wechat")==="bound")setNotice("微信账号绑定成功");
  }, []);
  useEffect(() => {
    if (!user || user.role === "merchant") return;
    setError(""); setNotice("");
    if (section === "videos") api<{items: Video[], total: number}>(`/videos?page=${page}&q=${encodeURIComponent(query)}`).then(r => {setVideos(r.items); setTotalVideos(r.total);}).catch(e => setError(e.message));
    if (section === "tasks") api<Task[]>("/tasks").then(setTasks).catch(e => setError(e.message));
    if (section === "upload") api<{id:number;title:string;order_no:string;status:string}[]>("/staff/publish-tasks").then(setPublishChoices).catch(e=>setError(e.message));
    if (section === "users" && user.role === "admin") api<User[]>("/users").then(setUsers).catch(e => setError(e.message));
    if (section === "system" && user.role === "admin") api<{items:typeof systemEvents}>("/system/audit-logs?limit=50").then(r=>setSystemEvents(r.items)).catch(e=>setError(e.message));
  }, [user, section, page, query]);

  async function login(e: FormEvent) {
    e.preventDefault(); setLoading(true); setError("");
    try { const u = await api<User>("/auth/login", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({email,password}) }); setUser(u); setPassword(""); setSection(u.role === "producer" || site === "video" ? "publish" : site === "deliver" ? "upload" : "dashboard"); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }
  async function logout() { await api("/auth/logout", {method:"POST"}); setUser(null); setSection("dashboard"); }
  async function upload(e: FormEvent) {
    e.preventDefault(); if (!uploadFile) return;
    setLoading(true); setError(""); setNotice("");
    const body = new FormData(); body.append("file", uploadFile);
    try {
      const endpoint=uploadToTask?`/staff/publish-tasks/${uploadToTask}/upload`:"/videos";
      await api(endpoint,{method:"POST",body});
      setNotice(uploadToTask?`已上传到发布任务，商家可以审核：${uploadFile.name}`:`视频已存入素材库：${uploadFile.name}`);
      setUploadFile(null);
    }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }
  async function remove(v: Video) {
    if (!confirm(`确定删除“${v.filename}”？此操作不可撤销。`)) return;
    try { await api(`/videos/${v.id}`, {method:"DELETE"}); setVideos(old => old.filter(x => x.id !== v.id)); setTotalVideos(n=>n-1); setNotice("已删除视频"); }
    catch(e) {setError((e as Error).message);}
  }
  async function addUser(e: FormEvent) {
    e.preventDefault(); setError("");
    try { await api("/users", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(newUser)}); setUsers(await api<User[]>("/users")); setNotice(newUser.role === "merchant" ? "商家账号创建成功，已关联独立商家档案" : "账号创建成功"); setNewUser({name:"",email:"",password:"",role:"producer",merchant_name:""}); }
    catch(e) {setError((e as Error).message);}
  }
  async function toggleUser(u:User) {
    setError("");
    try { await api(`/users/${u.id}/active`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({is_active:!u.is_active})}); setUsers(await api<User[]>("/users")); setNotice(u.is_active?"账号已停用":"账号已启用"); }
    catch(e) {setError((e as Error).message);}
  }

  if (!checked) return <div className="center">正在加载工作台…</div>;
  if (!user) return <main className="login-bg"><form className="login-card" onSubmit={login}>
    <img className="bm-login-logo" src="/brand-logo.png" alt="黑曼波猫咪 Logo" /><h1>黑曼波工作台</h1><p className="muted">管理员 · 拍摄剪辑 · 商家</p>
    {site!=="admin"&&<div className="wechat-register-block">
      <h3>微信授权登录 / 注册</h3>
      {wechatReady ? <>
        {site!=="video"&&<a className="wechat-button" href="/api/auth/wechat/start?role=merchant">微信注册 / 登录 · 商家</a>}
        <a className="wechat-button" href="/api/auth/wechat/start?role=producer">微信注册 / 登录 · 拍摄剪辑</a>
      </> : <p className="help">微信开放平台网站应用尚未配置。完成企业认证和网站应用审核，并在服务器配置 AppID / AppSecret 后即可启用。</p>}
    </div>}
    <div className="login-divider">{site==="admin"?"管理员账号登录":"已有账号登录"}</div>
    <label>邮箱账号<input type="email" required placeholder="admin@example.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label>登录密码<input type="password" required value={password} onChange={e=>setPassword(e.target.value)} /></label>
    {error && <div className="error">{error}</div>}<button className="primary full" disabled={loading}>{loading?"登录中…":"账号密码登录"}</button>
    <p className="help">{site==="admin"?"本入口只允许管理员账号登录。商家与拍摄剪辑请使用交付中心或视频工作台。":"商家和拍摄剪辑可微信自主注册；管理员也能在后台创建账号。商家审核统一在交付中心完成。"}</p>
  </form></main>;

  // The administrator owns every management surface. Other roles cannot enter
  // the main administrator domain, even if a login cookie is shared across subdomains.
  if (site === "admin" && user.role !== "admin") return <div className="center"><div className="panel site-access"><h2>这里是管理员总后台</h2><p>当前账号无权管理全站数据。请使用对应工作台。</p><a className="primary" href={user.role === "merchant"?domainLinks.deliver:domainLinks.video}>进入我的工作台</a><button className="textbtn" onClick={logout}>退出登录</button></div></div>;
  if (site === "video" && user.role === "merchant") return <div className="center"><div className="panel site-access"><h2>视频工作台仅限内部人员</h2><a className="primary" href={domainLinks.deliver}>进入商家交付中心</a></div></div>;
  if (user.role === "merchant") return <MerchantPortalV14 name={user.name} onLogout={logout}/>;
  if (site === "deliver" && user.role === "producer") return <div className="merchant-portal-shell"><header className="merchant-portal-header"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo"/><span>黑曼波交付中心<small>上传制作视频 · 查看商家审核与退回意见</small></span></div><div>{user.name}　<button className="textbtn" onClick={logout}>退出</button></div></header><main className="merchant-portal-content"><StaffPublishTasksV14 admin={false} producer={true}/></main></div>;


  return <div className="shell">
    <aside className="sidebar"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo" /><span>黑曼波工作台<small>视频与接单管理</small></span></div>
      <nav aria-label="工作台导航">{navGroups.map(g=>({...g,items:g.items.filter(m=>!m.adminOnly||user.role==="admin")})).filter(g=>g.items.length>0).map(g=><div key={g.title} className="nav-group"><div className="nav-group-title">{g.title}</div>{g.items.map(m=><button key={m.id} onClick={()=>{setSection(m.id);setPage(1);setNotice("");}} aria-current={section===m.id?"page":undefined} className={section===m.id?"nav active":"nav"}>{m.label}</button>)}</div>)}</nav>
      {user.role==="admin"&&<div className="sidebar-quick"><span>快捷入口</span>{site!=="test"&&<a href={workspaceHref("admin")}>返回管理总览</a>}<a href={workspaceHref("video")}>视频工作台 ↗</a><a href={workspaceHref("deliver")}>交付中心 ↗</a></div>}
      <div className="sidebar-foot">黑曼波工作台 V2.1.2 · 统一总后台<br/><small>同一套账号与业务数据</small></div>
    </aside>
    <main className="main"><header className="topbar"><div><strong>{menu.find(m=>m.id===section)?.label}</strong><span className="muted"> / 黑曼波工作台</span></div><div className="user">{user.name} <span className="role">{user.role==="admin"?"管理员":user.role==="producer"?"拍摄剪辑":"商家"}</span> <button className="textbtn" onClick={logout}>退出</button></div></header>
      <div className="content">{error && <div className="error">{error}</div>}{notice && <div className="success">{notice}</div>}
        {section==="dashboard" && user.role==="admin" && <><AdminOperations onNavigate={target=>{setSection(target);setNotice("");}}/><OrdersSummary onOpen={()=>setSection("orders")}/></>}
        {section==="merchants" && <MerchantsPanelV14 admin={user.role==="admin"}/>}
        {section==="publish" && <StaffPublishTasksV14 admin={user.role==="admin"} producer={user.role==="producer"}/>}
        {section==="orders" && user.role==="admin" && <><div className="order-center-tabs"><button className={orderTab==="ledger"?"active":""} onClick={()=>setOrderTab("ledger")}>订单台账与收款</button><button className={orderTab==="requests"?"active":""} onClick={()=>setOrderTab("requests")}>商家申请与需求</button></div>{orderTab==="ledger"?<OrdersPanel user={user}/>:<StaffProjectsV13 admin={true}/>}</>}
        {section==="client_projects" && <StaffProjectsV13 admin={user.role==="admin"}/>}
        {section==="videos" && <><div className="heading"><h1>视频管理</h1><p>在线预览、搜索和管理已上传视频</p></div><div className="toolbar"><input placeholder="搜索视频文件名" value={query} onChange={e=>{setPage(1);setQuery(e.target.value);}}/><div className="video-tools"><button className="secondary-btn" onClick={()=>setSection("tasks")}>上传记录</button><button className="primary" onClick={()=>setSection("upload")}>上传视频</button></div></div>
          <div className="panel tablewrap"><table><thead><tr><th>文件名称</th><th>大小</th><th>上传时间</th><th>状态</th><th>操作</th></tr></thead><tbody>{videos.map(v=><tr key={v.id}><td>{v.filename}</td><td>{bytes(v.size_bytes)}</td><td>{day(v.created_at)}</td><td><span className="status">{v.status==="deleted"?"已按商家确认清理":"已保存"}</span></td><td>{v.status!=="deleted"&&<button className="textbtn" onClick={()=>setActiveVideo(v)}>预览</button>}<button className="textbtn danger" disabled={v.status==="deleted"} onClick={()=>remove(v)}>删除</button></td></tr>)}{videos.length===0&&<tr><td colSpan={5} className="empty">暂无视频，先上传一个试试</td></tr>}</tbody></table></div>
          <div className="pager"><span>共 {totalVideos} 条</span><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>上一页</button><span>第 {page} 页</span><button disabled={page*20>=totalVideos} onClick={()=>setPage(p=>p+1)}>下一页</button></div>
        </>}
        {section==="upload" && <><div className="heading"><h1>上传制作视频</h1><p>可直接关联对应发布任务，商家登录后即可看到并审核；或仅保存到内部视频库。</p></div><form className="panel upload" onSubmit={upload}><div className="upload-icon">⇧</div><h3>选择制作好的视频</h3><label className="upload-destination">视频用途<select value={uploadToTask} onChange={e=>setUploadToTask(e.target.value)}><option value="">仅保存在内部素材库（商家不可见）</option>{publishChoices.filter(t=>t.status!=="published").map(t=><option value={t.id} key={t.id}>{t.order_no} · {t.title}（发布任务 #{t.id}）</option>)}</select></label><p className="muted">要让商家看到，必须选择已经关联订单和对应商家的发布任务。</p><input type="file" accept=".mp4,.mov,.webm,video/mp4,video/webm,video/quicktime" required onChange={e=>setUploadFile(e.target.files?.[0]||null)}/><button disabled={!uploadFile || loading || (!!uploadToTask && user.role!=="admin")} className="primary">{loading?"上传中…":uploadToTask?"上传并提交商家审核":"上传到视频库"}</button><small className="muted">单文件最大 100 MB。此版本不自动转码。</small></form></>}
        {section==="tasks" && <><div className="heading"><h1>任务中心</h1><p>查看最近 100 条上传任务记录</p></div><div className="panel tablewrap"><table><thead><tr><th>任务编号</th><th>类型</th><th>状态</th><th>详细信息</th><th>时间</th></tr></thead><tbody>{tasks.map(t=><tr key={t.id}><td>#{t.id}</td><td>{t.type}</td><td><span className="status">{t.status==="completed"?"已完成":t.status}</span></td><td>{t.detail}</td><td>{day(t.created_at)}</td></tr>)}{tasks.length===0&&<tr><td colSpan={5} className="empty">暂无任务记录</td></tr>}</tbody></table></div></>}
        {section==="system" && user.role==="admin" && <><div className="heading"><h1>操作记录</h1><p>管理员可以追溯账号、任务和订单相关操作。</p></div><div className="panel tablewrap"><table><thead><tr><th>时间</th><th>操作</th><th>对象</th><th>操作人ID</th></tr></thead><tbody>{systemEvents.map(event=><tr key={event.id}><td>{day(event.created_at)}</td><td>{event.action}</td><td>{event.target_type} {event.target_id}</td><td>{event.actor_id??"—"}</td></tr>)}{systemEvents.length===0&&<tr><td colSpan={4} className="empty">暂无可查看的操作记录</td></tr>}</tbody></table></div></>}
        {section==="users" && user.role==="admin" && <><div className="heading"><h1>账号管理</h1><p>管理员可创建三种账号；商家和拍摄剪辑仍可通过微信自主注册。</p></div><div className="panel"><h3>后台创建账号</h3><form className="user-form" onSubmit={addUser}><input placeholder="联系人 / 姓名" required value={newUser.name} onChange={e=>setNewUser({...newUser,name:e.target.value})}/><input type="email" placeholder="登录邮箱" required value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})}/><input type="password" minLength={12} placeholder="初始密码（至少12位）" required value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})}/><select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})}><option value="producer">拍摄剪辑</option><option value="merchant">商家</option><option value="admin">管理员</option></select>{newUser.role==="merchant"&&<input className="span2" placeholder="商家 / 公司名称（必填）" required maxLength={160} value={newUser.merchant_name} onChange={e=>setNewUser({...newUser,merchant_name:e.target.value})}/>}<button className="primary">创建账号</button></form><p className="help">商家后台创建后可使用邮箱密码登录，并能在自己的后台查看订单；可后续绑定微信。密码请通过安全渠道单独提供。</p></div><div className="panel tablewrap"><table><thead><tr><th>姓名</th><th>邮箱</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td>{u.name}</td><td>{u.email||"微信授权账号"}</td><td>{u.role==="admin"?"管理员":u.role==="producer"?"拍摄剪辑":"商家"}</td><td>{u.is_active?"启用":"已停用"}</td><td>{day(u.created_at)}</td><td><button className="textbtn" disabled={u.id===user.id} onClick={()=>toggleUser(u)}>{u.is_active?"停用账号":"启用账号"}</button></td></tr>)}</tbody></table></div></>}
      </div>
    </main>
    {activeVideo && activeVideo.status!=="deleted" && <div className="modal-bg" onClick={()=>setActiveVideo(null)}><div className="modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><strong>{activeVideo.filename}</strong><button onClick={()=>setActiveVideo(null)}>✕</button></div><video controls playsInline autoPlay src={activeVideo.stream_url} /><p className="muted">该视频需要使用支持对应编码的浏览器播放。</p></div></div>}
  </div>;
}
