"use client";
import {useEffect, useState, type FormEvent} from "react";
import {MerchantPublishTasksV14} from "./publish-tasks-v14";

type Merchant={id:number;name:string;category_id:number|null;category_name:string;contact_name:string;phone:string;address:string;platform_url:string;introduction:string;status:string};
type Detail=Merchant&{accounts:{id:number;email:string}[]};
type Category={id:number;name:string};
type Order={id:number;order_no:string;title:string;status:string;due_date:string|null};
const initial=()=>({name:"",category_id:"",contact_name:"",phone:"",address:"",platform_url:"",introduction:""});
async function api<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(`/api${path}`,{credentials:"include",cache:"no-store",...init});if(!r.ok){const e=await r.json().catch(()=>({}));throw Error(typeof e.detail==="string"?e.detail:`请求失败 ${r.status}`);}return r.json()}
const json=(v:unknown,method="POST"):RequestInit=>({method,headers:{"Content-Type":"application/json"},body:JSON.stringify(v)});

export function MerchantsPanelV14({admin}:{admin:boolean}){
  const [merchants,setMerchants]=useState<Merchant[]>([]),[cats,setCats]=useState<Category[]>([]),[detail,setDetail]=useState<Detail|null>(null);
  const [form,setForm]=useState(initial()),[mode,setMode]=useState<"new"|"edit"|null>(null),[search,setSearch]=useState("");
  const [account,setAccount]=useState({name:"",email:"",password:""}),[busy,setBusy]=useState(false),[error,setError]=useState(""),[ok,setOk]=useState("");
  const load=async()=>{const [m,c]=await Promise.all([api<{items:Merchant[]}>(`/merchants?limit=100&q=${encodeURIComponent(search)}`),api<Category[]>("/merchant-categories")]);setMerchants(m.items);setCats(c);};
  useEffect(()=>{load().catch(e=>setError(e.message));},[search]);
  const view=async(id:number)=>{setDetail(await api<Detail>(`/merchants/${id}`));};
  const act=async(fn:()=>Promise<unknown>,success:string)=>{setBusy(true);setError("");setOk("");try{await fn();await load();if(detail)await view(detail.id);setOk(success);}catch(e){setError((e as Error).message);}finally{setBusy(false)}};
  const save=async(e:FormEvent)=>{e.preventDefault();await act(async()=>{
    const payload={...form,category_id:form.category_id?Number(form.category_id):null};
    if(mode==="new")await api("/merchants",json(payload));else if(detail)await api(`/merchants/${detail.id}`,json(payload,"PATCH"));
    setMode(null);setForm(initial());},"商家资料已保存，无需资质审核即可关联订单");};
  const createAccount=async(e:FormEvent)=>{e.preventDefault();if(!detail)return;await act(async()=>{
    await api(`/merchants/${detail.id}/accounts`,json(account));setAccount({name:"",email:"",password:""});},"商家登录账号已创建，请安全地向客户交付密码");};
  return <div><div className="heading"><h1>商家与合作账号</h1><p>这里只维护合作商家和登录权限。商家不需要申请资质审核；商家负责审核我们交付的产品视频。</p></div>
    {error&&<div className="error">{error}</div>}{ok&&<div className="success">{ok}</div>}
    <div className="panel"><div className="toolbar"><input placeholder="搜索商家名称" value={search} onChange={e=>setSearch(e.target.value)}/>{admin&&<button className="primary" onClick={()=>{setMode("new");setDetail(null);setForm(initial());}}>＋ 新建商家</button>}</div>
      <div className="tablewrap"><table><thead><tr><th>商家名称</th><th>行业</th><th>联系人</th><th>合作状态</th><th>操作</th></tr></thead><tbody>{merchants.map(m=><tr key={m.id}><td>{m.name}</td><td>{m.category_name}</td><td>{m.contact_name||"—"}</td><td>{m.status==="suspended"?"已暂停":"合作中"}</td><td><button className="textbtn" onClick={()=>view(m.id)}>查看 / 设置账号</button></td></tr>)}{!merchants.length&&<tr><td className="empty" colSpan={5}>暂无商家。先新建商家，再将订单关联到商家。</td></tr>}</tbody></table></div>
    </div>
    {detail&&mode===null&&<div className="panel"><div className="toolbar"><h3>{detail.name} · 商家账号</h3><button className="secondary-btn" onClick={()=>setDetail(null)}>关闭</button></div>
      <p>联系人：{detail.contact_name||"—"}　电话：{detail.phone||"—"}　合作状态：{detail.status==="suspended"?"已暂停":"合作中"}</p>
      <p className="muted">发布任务关联的订单属于该商家时，商家账号才能预览并审核对应视频；其他商家不可查看。</p>
      {admin&&<><div className="toolbar"><button className="secondary-btn" onClick={()=>{setMode("edit");setForm({...initial(),...detail,category_id:detail.category_id?String(detail.category_id):""});}}>编辑资料</button>
        <button className="secondary-btn" disabled={busy} onClick={()=>act(()=>api(`/merchants/${detail.id}/access`,json({suspended:detail.status!=="suspended"})),detail.status==="suspended"?"已恢复商家合作":"已暂停商家登录权限")}>{detail.status==="suspended"?"恢复合作":"暂停合作"}</button></div>
        <h4>商家登录账户</h4>{detail.accounts.map(a=><p key={a.id}>{a.email}</p>)}
        <form className="user-form" onSubmit={createAccount}><input required placeholder="商家联系人姓名" value={account.name} onChange={e=>setAccount({...account,name:e.target.value})}/><input type="email" required placeholder="商家登录邮箱" value={account.email} onChange={e=>setAccount({...account,email:e.target.value})}/><input type="password" minLength={12} required placeholder="初始密码（≥12位）" value={account.password} onChange={e=>setAccount({...account,password:e.target.value})}/><button className="primary" disabled={busy}>创建账号</button></form>
      </>}
    </div>}
    {mode!==null&&<div className="modal-bg" onClick={()=>setMode(null)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}><h3>{mode==="new"?"新增合作商家":"修改商家资料"}</h3>
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
  const [tab,setTab]=useState<"review"|"orders"|"profile">("review"),[profile,setProfile]=useState<Merchant|null>(null),[orders,setOrders]=useState<Order[]>([]),[error,setError]=useState("");
  useEffect(()=>{Promise.all([api<Merchant>("/portal/me"),api<Order[]>("/portal/orders")]).then(([m,o])=>{setProfile(m);setOrders(o);}).catch(e=>setError(e.message));},[]);
  return <div className="merchant-portal-shell"><header className="merchant-portal-header"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo"/><span>黑曼波工作台<small>商家视频审核中心</small></span></div><div>{name}　<button className="textbtn" onClick={onLogout}>退出</button></div></header>
    <main className="merchant-portal-content"><div className="heading"><h1>{profile?.name||"商家工作台"}</h1><p>你负责审核我们为你的产品制作的视频，只有你们商家的发布任务会显示在这里。</p></div>
      {error&&<div className="error">{error}</div>}
      <div className="pub-tabs"><button className={tab==="review"?"active":""} onClick={()=>setTab("review")}>待审核视频 / 发布任务</button><button className={tab==="orders"?"active":""} onClick={()=>setTab("orders")}>我的合作订单</button><button className={tab==="profile"?"active":""} onClick={()=>setTab("profile")}>合作资料</button></div>
      {tab==="review"&&<MerchantPublishTasksV14/>}
      {tab==="orders"&&<div className="panel tablewrap"><table><thead><tr><th>订单编号</th><th>项目</th><th>制作状态</th><th>交付日期</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>{o.order_no}</td><td>{o.title}</td><td>{o.status}</td><td>{o.due_date||"—"}</td></tr>)}{!orders.length&&<tr><td colSpan={4} className="empty">暂无关联订单</td></tr>}</tbody></table></div>}
      {tab==="profile"&&<div className="panel"><h3>合作资料</h3><p>商家名称：{profile?.name||"—"}</p><p>联系人：{profile?.contact_name||"—"}</p><p>联系方式：{profile?.phone||"—"}</p><p>合作状态：{profile?.status==="suspended"?"已暂停":"合作中"}</p><p className="muted">需要修改资料或账号，请联系黑曼波团队。不再需要商家资质申请或资质审核。</p></div>}
    </main></div>;
}
