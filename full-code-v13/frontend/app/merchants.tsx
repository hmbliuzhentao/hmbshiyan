"use client";
import {useEffect, useMemo, useState, type FormEvent} from "react";
import {MerchantProjectsV13} from "./merchant-projects-v13";

type MerchantStatus = "draft"|"pending"|"changes_requested"|"approved"|"rejected"|"suspended";
type Category = {id:number;name:string;parent_id:number|null};
type Merchant = {id:number;name:string;category_id:number|null;category_name:string;contact_name:string;phone:string;address:string;platform_url:string;introduction:string;status:MerchantStatus;review_reason:string;submitted_at:string|null;reviewed_at:string|null;created_at:string};
type MerchantDetail = Merchant & {reviews:{id:number;old_status:string;new_status:string;note:string;created_at:string}[];accounts:{id:number;email:string}[]};
type MerchantStats = {total:number;status_counts:Record<string,number>;categories:{category:string;count:number}[]};
const statuses:Record<MerchantStatus,string> = {draft:"草稿",pending:"待审核",changes_requested:"待补资料",approved:"已通过",rejected:"已驳回",suspended:"已暂停"};
const empty=()=>({name:"",category_id:"",contact_name:"",phone:"",address:"",platform_url:"",introduction:""});
type Form=ReturnType<typeof empty>;
async function api<T>(path:string, init?:RequestInit):Promise<T>{
  const r=await fetch(`/api${path}`,{credentials:"include",...init});
  if(!r.ok){const x=await r.json().catch(()=>null);throw Error(typeof x?.detail==="string"?x.detail:`请求失败 ${r.status}`);}
  return r.json();
}
const json=(data:unknown):RequestInit=>({headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});

export function MerchantsPanel({reviewOnly=false,admin}:{reviewOnly?:boolean;admin:boolean}){
  const [list,setList]=useState<Merchant[]>([]),[stats,setStats]=useState<MerchantStats|null>(null),[categories,setCategories]=useState<Category[]>([]);
  const [search,setSearch]=useState(""),[filter,setFilter]=useState(reviewOnly?"pending":""),[categoryFilter,setCategoryFilter]=useState("");
  const [detail,setDetail]=useState<MerchantDetail|null>(null),[editing,setEditing]=useState<null|"new"|number>(null),[form,setForm]=useState<Form>(empty());
  const [reason,setReason]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[success,setSuccess]=useState("");
  const [login,setLogin]=useState({name:"",email:"",password:""}),[newCategory,setNewCategory]=useState("");
  const load=async()=>{
    const params=new URLSearchParams();if(search)params.set("q",search);if(filter)params.set("status",filter);if(categoryFilter)params.set("category_id",categoryFilter);
    const [items,summary,cats]=await Promise.all([api<{items:Merchant[]}>(`/merchants?${params}`),api<MerchantStats>("/merchants/stats"),api<Category[]>("/merchant-categories")]);
    setList(items.items);setStats(summary);setCategories(cats);
  };
  useEffect(()=>{load().catch(e=>setError(e.message));},[filter,categoryFilter,search]);
  const open=async(id:number)=>{setError("");setSuccess("");setDetail(await api<MerchantDetail>(`/merchants/${id}`));setReason("");};
  const startEdit=(m?:Merchant)=>{setEditing(m?m.id:"new");setDetail(null);setForm(m?{name:m.name,category_id:m.category_id?String(m.category_id):"",contact_name:m.contact_name,phone:m.phone,address:m.address,platform_url:m.platform_url,introduction:m.introduction}:empty());};
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");try{
    const values={...form,category_id:form.category_id?Number(form.category_id):null};
    if(editing==="new")await api("/merchants",{method:"POST",...json(values)});
    else await api(`/merchants/${editing}`,{method:"PATCH",...json(values)});
    setEditing(null);setSuccess("商家档案已保存");await load();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const act=async(path:string,payload?:unknown)=>{setBusy(true);setError("");try{
    await api(path,{method:"POST",...(payload?json(payload):{})});setSuccess("操作已完成");
    await load();if(detail)await open(detail.id);
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const addAccount=async(e:FormEvent)=>{e.preventDefault();if(!detail)return;await act(`/merchants/${detail.id}/accounts`,login);setLogin({name:"",email:"",password:""});};
  const addCategory=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");try{await api("/merchant-categories",{method:"POST",...json({name:newCategory})});setNewCategory("");await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const categoryOptions=useMemo(()=>categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>),[categories]);
  return <div className="orders-root">
    <div className="heading order-heading"><div><h1>{reviewOnly?"商家审核中心":"商家分类与档案"}</h1><p>{reviewOnly?"核对商家信息 · 审核结果留痕":"按行业归类、维护商家资料、关联视频制作订单"}</p></div>
      {admin&&!reviewOnly&&<button className="primary" onClick={()=>startEdit()}>＋ 新增商家</button>}
    </div>
    {error&&<div className="error">{error}</div>}{success&&<div className="success">{success}</div>}
    <div className="order-metrics">{[
      ["商家总数",stats?.total??"—"],["待审核",stats?.status_counts.pending??"—"],["审核通过",stats?.status_counts.approved??"—"],
      ["待补资料",stats?.status_counts.changes_requested??"—"],["已驳回",stats?.status_counts.rejected??"—"],["已暂停",stats?.status_counts.suspended??"—"]
    ].map(([title,count])=><div className="panel order-metric" key={title}><span>{title}</span><strong>{count}</strong></div>)}</div>
    {!reviewOnly&&<div className="panel"><h3>行业分类分布</h3><div className="merchant-categories">{stats?.categories.length?stats.categories.map(c=><span key={c.category}>{c.category} <b>{c.count}</b></span>):<span className="muted">暂无商家数据</span>}</div>
      {admin&&<form onSubmit={addCategory} className="merchant-inline"><input placeholder="新增行业分类" maxLength={80} required value={newCategory} onChange={e=>setNewCategory(e.target.value)}/><button disabled={busy} className="secondary-btn">添加分类</button></form>}
    </div>}
    <div className="panel merchant-filters"><input placeholder="搜索商家名称 / 联系人" value={search} onChange={e=>setSearch(e.target.value)}/>
      <select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">全部审核状态</option>{Object.entries(statuses).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
      <select value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}><option value="">全部行业</option>{categoryOptions}</select>
      <button className="secondary-btn" onClick={()=>{setSearch("");setFilter(reviewOnly?"pending":"");setCategoryFilter("");}}>重置筛选</button>
    </div>
    <div className="panel tablewrap"><table><thead><tr><th>商家</th><th>行业</th><th>联系人</th><th>审核状态</th><th>创建时间</th><th>操作</th></tr></thead><tbody>
      {list.map(m=><tr key={m.id}><td><strong>{m.name}</strong><div className="muted">编号 #{m.id}</div></td><td>{m.category_name}</td><td>{m.contact_name||"—"}</td><td><span className={`merchant-status ${m.status}`}>{statuses[m.status]}</span></td><td>{m.created_at?.slice(0,10)}</td><td><button className="textbtn" onClick={()=>open(m.id).catch(e=>setError(e.message))}>查看 / 审核</button></td></tr>)}
      {!list.length&&<tr><td colSpan={6} className="empty">暂无符合条件的商家</td></tr>}
    </tbody></table></div>
    {editing!==null&&<div className="modal-bg" onClick={()=>setEditing(null)}><div className="modal merchant-modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><h3>{editing==="new"?"新增商家档案":"编辑商家资料"}</h3><button onClick={()=>setEditing(null)}>✕</button></div>
      <form className="order-form" onSubmit={submit}>
        <label>商家名称 *<input required maxLength={160} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
        <label>行业分类<select value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})}><option value="">待分类</option>{categoryOptions}</select></label>
        <label>联系人<input maxLength={80} value={form.contact_name} onChange={e=>setForm({...form,contact_name:e.target.value})}/></label>
        <label>联系电话<input maxLength={60} value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
        <label className="span2">门店/公司地址<input maxLength={250} value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></label>
        <label className="span2">平台主页链接<input maxLength={400} value={form.platform_url} onChange={e=>setForm({...form,platform_url:e.target.value})}/></label>
        <label className="span2">商家介绍 / 合作需求<textarea rows={3} maxLength={1500} value={form.introduction} onChange={e=>setForm({...form,introduction:e.target.value})}/></label>
        <div className="span2 order-modal-actions"><button type="button" className="secondary-btn" onClick={()=>setEditing(null)}>取消</button><button disabled={busy} className="primary">保存档案</button></div>
      </form></div></div>}
    {detail&&<div className="modal-bg" onClick={()=>setDetail(null)}><div className="modal merchant-modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><div><h3>{detail.name}</h3><p className="muted">#{detail.id} · {detail.category_name} · {statuses[detail.status]}</p></div><button onClick={()=>setDetail(null)}>✕</button></div>
      <div className="merchant-details"><p>联系人：{detail.contact_name||"—"}　电话：{detail.phone||"—"}</p><p>地址：{detail.address||"—"}</p><p>主页：{detail.platform_url||"—"}</p><p>商家介绍：{detail.introduction||"—"}</p>{detail.review_reason&&<p className="merchant-alert">最近审核意见：{detail.review_reason}</p>}</div>
      {admin&&<div className="merchant-actions"><button className="secondary-btn" onClick={()=>startEdit(detail)}>修改资料</button>{["draft","changes_requested","rejected"].includes(detail.status)&&<button className="primary" disabled={busy} onClick={()=>act(`/merchants/${detail.id}/submit`)}>提交审核</button>}</div>}
      {admin&&["pending","approved"].includes(detail.status)&&<div className="panel merchant-review"><h3>{detail.status==="pending"?"审核操作":"商家状态管理"}</h3>
        <label>审核意见<textarea rows={2} maxLength={500} placeholder="驳回、要求补充或暂停时必须填写原因" value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <div className="merchant-actions">{detail.status==="pending"&&<><button disabled={busy} className="primary" onClick={()=>act(`/merchants/${detail.id}/review`,{decision:"approved",reason})}>审核通过</button><button disabled={busy||!reason.trim()} className="secondary-btn" onClick={()=>act(`/merchants/${detail.id}/review`,{decision:"changes_requested",reason})}>要求补资料</button><button disabled={busy||!reason.trim()} className="secondary-btn" onClick={()=>act(`/merchants/${detail.id}/review`,{decision:"rejected",reason})}>驳回</button></>}
        {detail.status==="approved"&&<button disabled={busy||!reason.trim()} className="secondary-btn" onClick={()=>act(`/merchants/${detail.id}/review`,{decision:"suspended",reason})}>暂停合作</button>}</div>
      </div>}
      {admin&&<div className="panel merchant-account"><h3>商家端登录账号</h3><p className="muted">该账号只能访问本商家的资料、审核状态和关联订单，不可查看内部成本、其他商家或内部视频。</p>
        {detail.accounts.map(a=><p key={a.id}>{a.email}</p>)}
        <form onSubmit={addAccount} className="merchant-inline"><input required placeholder="登录人姓名" value={login.name} onChange={e=>setLogin({...login,name:e.target.value})}/><input type="email" required placeholder="商家邮箱" value={login.email} onChange={e=>setLogin({...login,email:e.target.value})}/><input type="password" minLength={12} required placeholder="初始密码（12位以上）" value={login.password} onChange={e=>setLogin({...login,password:e.target.value})}/><button disabled={busy} className="primary">创建账号</button></form>
      </div>}
      <h3>审核记录</h3><div className="order-history">{detail.reviews.map(r=><div key={r.id}><span>{statuses[r.old_status as MerchantStatus]||r.old_status} → {statuses[r.new_status as MerchantStatus]||r.new_status}：{r.note||"无备注"}</span><small>{r.created_at?.slice(0,19).replace("T"," ")}</small></div>)}{!detail.reviews.length&&<p className="muted">暂无审核记录</p>}</div>
    </div></div>}
  </div>;
}

// Merchant-facing UI uses only /api/portal/* endpoints and never requests staff statistics.
type PortalOrder = {id:number;order_no:string;title:string;service_type:string;status:string;order_date:string;due_date:string|null;amount_cents:number;paid_cents:number;outstanding_cents:number};
const money=(c:number)=>(c/100).toLocaleString("zh-CN",{style:"currency",currency:"CNY"});
export function MerchantPortal({name,onLogout}:{name:string;onLogout:()=>void}){
  const [profile,setProfile]=useState<Merchant|null>(null),[cats,setCats]=useState<Category[]>([]),[orders,setOrders]=useState<PortalOrder[]>([]);
  const [form,setForm]=useState<Form>(empty()),[editing,setEditing]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState(""),[loading,setLoading]=useState(false);
  const refresh=async()=>{const [p,c,o]=await Promise.all([api<Merchant>("/portal/me"),api<Category[]>("/merchant-categories"),api<PortalOrder[]>("/portal/orders")]);
    setProfile(p);setCats(c);setOrders(o);setForm({name:p.name,category_id:p.category_id?String(p.category_id):"",contact_name:p.contact_name,phone:p.phone,address:p.address,platform_url:p.platform_url,introduction:p.introduction});};
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[]);
  const save=async(e:FormEvent)=>{e.preventDefault();setLoading(true);setError("");try{await api("/portal/profile",{method:"PATCH",...json({...form,category_id:form.category_id?Number(form.category_id):null})});await refresh();setNotice("资料已保存。修改资料后请重新提交审核。");setEditing(false);}catch(e){setError((e as Error).message);}finally{setLoading(false);}};
  const submit=async()=>{setLoading(true);setError("");try{await api("/portal/submit",{method:"POST"});await refresh();setNotice("资料已提交，等待工作人员审核。");}catch(e){setError((e as Error).message);}finally{setLoading(false);}};
  return <div className="merchant-portal-shell"><header className="merchant-portal-header"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo" /><span>黑曼波工作台<small>商家服务中心</small></span></div><div><span className="muted">{name}</span> <button className="textbtn" onClick={onLogout}>退出登录</button></div></header>
    <main className="merchant-portal-content"><div className="heading"><h1>我的商家工作台</h1><p>商家资料 · 所属行业 · 审核进度 · 我们合作的订单</p></div>
      {error&&<div className="error">{error}</div>}{notice&&<div className="success">{notice}</div>}
      {profile&&<><div className="merchant-hero panel"><div><p className="muted">当前商家</p><h2>{profile.name}</h2><p>{profile.category_name}</p></div><div><span className={`merchant-status ${profile.status}`}>{statuses[profile.status]}</span>{profile.review_reason&&<p className="merchant-alert">审核意见：{profile.review_reason}</p>}</div></div>
      <div className="panel"><div className="order-inline"><div><h3>商家基本资料</h3><p className="muted">由商家维护资料，由工作人员负责审核</p></div><button className="secondary-btn" disabled={profile.status==="suspended"} onClick={()=>setEditing(s=>!s)}>{editing?"取消编辑":"修改资料"}</button></div>
        {editing?<form className="order-form" onSubmit={save}><label>商家名称<input required maxLength={160} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
          <label>行业分类<select value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})}><option value="">请选择</option>{cats.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label>联系人<input value={form.contact_name} onChange={e=>setForm({...form,contact_name:e.target.value})}/></label><label>联系电话<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
          <label className="span2">地址<input value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></label><label className="span2">平台主页<input value={form.platform_url} onChange={e=>setForm({...form,platform_url:e.target.value})}/></label>
          <label className="span2">介绍<textarea rows={3} value={form.introduction} onChange={e=>setForm({...form,introduction:e.target.value})}/></label>
          <div className="span2"><button disabled={loading} className="primary">保存修改</button></div></form>
        :<div className="merchant-details"><p>联系人：{profile.contact_name||"未填写"}</p><p>电话：{profile.phone||"未填写"}</p><p>地址：{profile.address||"未填写"}</p><p>平台主页：{profile.platform_url||"未填写"}</p><p>介绍：{profile.introduction||"未填写"}</p></div>}
        {["draft","changes_requested","rejected"].includes(profile.status)&&<div className="merchant-submit"><p className="muted">确认商家信息无误后提交给平台工作人员审核。</p><button className="primary" disabled={loading||!profile.category_id} onClick={submit}>提交商家审核</button></div>}
      </div></>}
      <MerchantProjectsV13 approved={profile?.status === "approved"}/>
      <div className="panel tablewrap"><h3>我的合作订单</h3><p className="muted">只能看到本商家的订单；内部成本、员工管理和其他商家数据不对外展示。</p><table><thead><tr><th>订单编号</th><th>制作项目</th><th>进度</th><th>约定金额</th><th>已收款</th><th>计划交付</th></tr></thead><tbody>
        {orders.map(o=><tr key={o.id}><td>{o.order_no}</td><td>{o.title}<div className="muted">{o.service_type}</div></td><td>{({confirmed:"已确认",in_progress:"制作中",delivered:"已交付",closed:"已结单",cancelled:"已取消"} as Record<string,string>)[o.status]||o.status}</td><td>{money(o.amount_cents)}</td><td>{money(o.paid_cents)}</td><td>{o.due_date||"—"}</td></tr>)}
        {!orders.length&&<tr><td className="empty" colSpan={6}>暂无已关联的合作订单</td></tr>}
      </tbody></table></div>
    </main></div>;
}
