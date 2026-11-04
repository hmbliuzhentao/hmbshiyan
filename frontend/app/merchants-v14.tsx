"use client";
import {useEffect, useState, type FormEvent} from "react";
import {MerchantPublishTasksV14} from "./publish-tasks-v14";
import {MerchantProjectsV13} from "./merchant-projects-v13";

type Merchant={id:number;name:string;category_id:number|null;category_name:string;contact_name:string;phone:string;address:string;platform_url:string;introduction:string;status:string};
type Detail=Merchant&{accounts:{id:number;email:string;name:string;role:string;is_active:boolean}[]};
type Category={id:number;name:string};
type Order={id:number;order_no:string;title:string;status:string;due_date:string|null};
const initial=()=>({name:"",category_id:"",contact_name:"",phone:"",address:"",platform_url:"",introduction:""});
async function api<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(`/api${path}`,{credentials:"include",cache:"no-store",...init});if(!r.ok){const e=await r.json().catch(()=>({}));throw Error(typeof e.detail==="string"?e.detail:`请求失败 ${r.status}`);}return r.json()}
const json=(v:unknown,method="POST"):RequestInit=>({method,headers:{"Content-Type":"application/json"},body:JSON.stringify(v)});

export function MerchantsPanelV14({admin}:{admin:boolean}){
  const [merchants,setMerchants]=useState<Merchant[]>([]),[cats,setCats]=useState<Category[]>([]),[detail,setDetail]=useState<Detail|null>(null);
  const [form,setForm]=useState(initial()),[mode,setMode]=useState<"edit"|null>(null),[search,setSearch]=useState("");
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[ok,setOk]=useState("");
  const [showCreate,setShowCreate]=useState(false);
  const [account,setAccount]=useState({merchant_name:"",name:"",email:"",password:""});
  const load=async()=>{const [m,c]=await Promise.all([api<{items:Merchant[]}>(`/merchants?limit=100&q=${encodeURIComponent(search)}`),api<Category[]>("/merchant-categories")]);setMerchants(m.items);setCats(c);};
  useEffect(()=>{load().catch(e=>setError(e.message));},[search]);
  const view=async(id:number)=>{setDetail(await api<Detail>(`/merchants/${id}`));};
  const act=async(fn:()=>Promise<unknown>,success:string)=>{setBusy(true);setError("");setOk("");try{await fn();await load();if(detail)await view(detail.id);setOk(success);}catch(e){setError((e as Error).message);}finally{setBusy(false)}};
  const save=async(e:FormEvent)=>{e.preventDefault();await act(async()=>{
    const payload={...form,category_id:form.category_id?Number(form.category_id):null};
    if(detail)await api(`/merchants/${detail.id}`,json(payload,"PATCH"));
    setMode(null);setForm(initial());},"商家资料已保存，无需资质审核即可关联订单");};
  const createAccount=async(e:FormEvent)=>{e.preventDefault();await act(async()=>{
    await api("/users",json({...account,role:"merchant"}));
    setAccount({merchant_name:"",name:"",email:"",password:""});
    setShowCreate(false);
  },"商家账号已创建，可直接用邮箱密码登录；独立商家档案已关联");};
  return <div><div className="heading"><h1>商家管理</h1><p>每位商家只能查看自己的订单与视频；无需审核即可使用。</p></div>
    {error&&<div className="error">{error}</div>}{ok&&<div className="success">{ok}</div>}
    {admin&&<div className="panel"><div className="toolbar"><div><h3 style={{marginBottom:4}}>商家账号</h3><p className="muted" style={{margin:0,fontSize:12}}>微信自主注册或管理员后台创建，两种方式都保留。</p></div><button className="primary" type="button" onClick={()=>setShowCreate(v=>!v)}>{showCreate?"收起":"新建商家账号"}</button></div>
      {showCreate&&<form className="order-form" onSubmit={createAccount}>
        <label>商家 / 公司名称<input required maxLength={160} value={account.merchant_name} onChange={e=>setAccount({...account,merchant_name:e.target.value})}/></label>
        <label>联系人<input required maxLength={80} value={account.name} onChange={e=>setAccount({...account,name:e.target.value})}/></label>
        <label>登录邮箱<input required type="email" value={account.email} onChange={e=>setAccount({...account,email:e.target.value})}/></label>
        <label>初始密码<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" placeholder="至少12位" value={account.password} onChange={e=>setAccount({...account,password:e.target.value})}/></label>
        <div className="span2"><button disabled={busy} className="primary">{busy?"创建中…":"创建并开通商家账号"}</button><p className="help" style={{marginTop:9}}>创建后无需审核即可登录，初始密码请通过安全渠道告知商家；后续可绑定微信。</p></div>
      </form>}
    </div>}
    <div className="panel"><div className="toolbar"><input placeholder="搜索商家名称" value={search} onChange={e=>setSearch(e.target.value)}/></div>
      <div className="tablewrap"><table><thead><tr><th>商家名称</th><th>行业</th><th>联系人</th><th>合作状态</th><th>操作</th></tr></thead><tbody>{merchants.map(m=><tr key={m.id}><td>{m.name}</td><td>{m.category_name}</td><td>{m.contact_name||"—"}</td><td>{m.status==="suspended"?"已暂停":"合作中"}</td><td><button className="textbtn" onClick={()=>view(m.id)}>查看商家资料</button></td></tr>)}{!merchants.length&&<tr><td className="empty" colSpan={5}>暂无商家。管理员可以在上方创建商家账号，也可以由商家微信自主注册。</td></tr>}</tbody></table></div>
    </div>
    {detail&&mode===null&&<div className="panel"><div className="toolbar"><h3>{detail.name} · 商家账号</h3><button className="secondary-btn" onClick={()=>setDetail(null)}>关闭</button></div>
      <p>联系人：{detail.contact_name||"—"}　电话：{detail.phone||"—"}　合作状态：{detail.status==="suspended"?"已暂停":"合作中"}</p>
      <p className="muted">发布任务关联的订单属于该商家时，商家账号才能预览并审核对应视频；其他商家不可查看。</p>
      {admin&&<><div className="toolbar"><button className="secondary-btn" onClick={()=>{setMode("edit");setForm({...initial(),...detail,category_id:detail.category_id?String(detail.category_id):""});}}>编辑资料</button>
        <button className="secondary-btn" disabled={busy} onClick={()=>act(()=>api(`/merchants/${detail.id}/access`,json({suspended:detail.status!=="suspended"})),detail.status==="suspended"?"已恢复商家合作":"已暂停商家登录权限")}>{detail.status==="suspended"?"恢复合作":"暂停合作"}</button></div>
        <h4>已关联登录账户</h4>{detail.accounts.map(a=><p key={a.id}>{a.name||a.email}　<span className="muted">{a.role==="merchant"?"商家":"其他角色"} · {a.is_active?"启用":"已停用"}</span>{a.email?` · ${a.email}`:" · 微信账号"}</p>)}
        <p className="muted">商家可自行使用微信注册，管理员也可以在此创建商家账号。两种方式均自动关联独立商家档案，无需审核。</p>
      </>}
    </div>}
    {mode!==null&&<div className="modal-bg" onClick={()=>setMode(null)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}><h3>修改商家资料</h3>
      <form className="order-form" onSubmit={save}><label>商家名称<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
        <label>行业分类<select value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})}><option value="">不分类</option>{cats.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label>联系人<input value={form.contact_name} onChange={e=>setForm({...form,contact_name:e.target.value})}/></label><label>电话<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
        <label className="span2">地址<input value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></label>
        <label className="span2">产品主页<input value={form.platform_url} onChange={e=>setForm({...form,platform_url:e.target.value})}/></label>
        <label className="span2">备注<textarea rows={2} value={form.introduction} onChange={e=>setForm({...form,introduction:e.target.value})}/></label>
        <button className="secondary-btn" type="button" onClick={()=>setMode(null)}>取消</button><button className="primary" disabled={busy}>保存商家</button></form>
    </div></div>}
  </div>;
}

export function MerchantPortalV14({name,onLogout}:{name:string;onLogout:()=>void}){
  const [tab,setTab]=useState<"create"|"review"|"orders"|"profile">("create"),[profile,setProfile]=useState<Merchant|null>(null),[orders,setOrders]=useState<Order[]>([]),[error,setError]=useState(""),[message,setMessage]=useState(""),[saving,setSaving]=useState(false),[wechatBound,setWechatBound]=useState(false);
  const [profileForm,setProfileForm]=useState({name:"",contact_name:"",phone:"",address:"",platform_url:"",introduction:""});
  useEffect(()=>{Promise.all([api<Merchant>("/portal/me"),api<Order[]>("/portal/orders"),api<{wechat_bound:boolean}>("/auth/identities")]).then(([m,o,identities])=>{setProfile(m);setOrders(o);setWechatBound(!!identities.wechat_bound);setProfileForm({name:m.name||"",contact_name:m.contact_name||"",phone:m.phone||"",address:m.address||"",platform_url:m.platform_url||"",introduction:m.introduction||""});}).catch(e=>setError(e.message));const params=new URLSearchParams(window.location.search);if(params.get("wechat")==="bound")setMessage("微信账号绑定成功");const code=params.get("error");if(code)setError("微信授权未完成，请重新扫码或联系管理员。");},[]);
  const saveProfile=async(e:FormEvent)=>{e.preventDefault();setSaving(true);setError("");setMessage("");try{const updated=await api<Merchant>("/portal/profile",json(profileForm,"PATCH"));setProfile(updated);setMessage("商家资料已保存");}catch(e){setError((e as Error).message);}finally{setSaving(false);}};
  useEffect(()=>{if(tab==="orders")api<Order[]>("/portal/orders").then(setOrders).catch(e=>setError(e.message));},[tab]);
  return <div className="merchant-portal-shell"><header className="merchant-portal-header"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo"/><span>黑曼波交付中心<small>订单申请 · 视频审核 · 退回修改</small></span></div><div>{name}　<button className="textbtn" onClick={onLogout}>退出</button></div></header>
    <main className="merchant-portal-content"><div className="heading"><h1>{profile?.name||"商家工作台"}</h1><p>你发布订单与视频任务，黑曼波团队负责制作交付；你负责审核视频并登记发布。</p></div>
      {error&&<div className="error">{error}</div>}
      <div className="pub-tabs"><button className={tab==="create"?"active":""} onClick={()=>setTab("create")}>发布订单</button><button className={tab==="review"?"active":""} onClick={()=>setTab("review")}>发布任务 / 审核视频</button><button className={tab==="orders"?"active":""} onClick={()=>setTab("orders")}>我的合作订单</button><button className={tab==="profile"?"active":""} onClick={()=>setTab("profile")}>合作资料</button></div>
      {tab==="create"&&<MerchantProjectsV13 approved={!!profile&&profile.status!=="suspended"}/>}
      {tab==="review"&&<MerchantPublishTasksV14/>}
      {tab==="orders"&&<div className="panel tablewrap"><table><thead><tr><th>订单编号</th><th>项目</th><th>制作状态</th><th>交付日期</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>{o.order_no}</td><td>{o.title}</td><td>{o.status}</td><td>{o.due_date||"—"}</td></tr>)}{!orders.length&&<tr><td colSpan={4} className="empty">暂无关联订单</td></tr>}</tbody></table></div>}
      {tab==="profile"&&<div className="panel"><h3>完善商家资料</h3><p className="muted">微信注册后自动开通，无需人工审核。请完善公司与联系人信息，便于管理员处理订单。</p>{message&&<div className="success">{message}</div>}<form className="order-form" onSubmit={saveProfile}><label>商家 / 公司名称<input required maxLength={160} value={profileForm.name} onChange={e=>setProfileForm({...profileForm,name:e.target.value})}/></label><label>联系人<input maxLength={80} value={profileForm.contact_name} onChange={e=>setProfileForm({...profileForm,contact_name:e.target.value})}/></label><label>联系电话<input maxLength={60} value={profileForm.phone} onChange={e=>setProfileForm({...profileForm,phone:e.target.value})}/></label><label>地址<input maxLength={250} value={profileForm.address} onChange={e=>setProfileForm({...profileForm,address:e.target.value})}/></label><label className="span2">店铺 / 产品主页<input maxLength={400} value={profileForm.platform_url} onChange={e=>setProfileForm({...profileForm,platform_url:e.target.value})}/></label><label className="span2">合作说明<textarea rows={3} maxLength={1500} value={profileForm.introduction} onChange={e=>setProfileForm({...profileForm,introduction:e.target.value})}/></label><button className="primary" disabled={saving}>{saving?"保存中…":"保存商家资料"}</button></form><p className="muted">合作状态：{profile?.status==="suspended"?"已暂停":"合作中"}</p><div className="toolbar"><span>{wechatBound?"微信已绑定":"尚未绑定微信"}</span>{!wechatBound&&<a className="wechat-button" href="/api/auth/wechat/start?mode=bind">绑定微信登录</a>}</div></div>}
    </main></div>;
}
