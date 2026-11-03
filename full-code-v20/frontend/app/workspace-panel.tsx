"use client";

import {useCallback, useEffect, useState, type FormEvent} from "react";

type RecordItem={
  id:number;title:string;body:string;status:string;merchant_id:number|null;
  created_at:string;updated_at?:string
};
type Merchant={id:number;name:string};
type Props={kind:string;label:string;canWrite:boolean};
type FormShape={title:string;body:string;status:string;merchant_id:string};
const emptyForm=():FormShape=>({title:"",body:"",status:"draft",merchant_id:""});

async function request<T>(path:string,init?:RequestInit):Promise<T>{
  const res=await fetch(`/api${path}`,{credentials:"include",cache:"no-store",...init});
  if(!res.ok){
    const data=await res.json().catch(()=>({}));
    throw Error(typeof data.detail==="string"?data.detail:`操作失败（HTTP ${res.status}）`);
  }
  return res.json();
}

export default function WorkspacePanel({kind,label,canWrite}:Props){
  const [items,setItems]=useState<RecordItem[]>([]);
  const [merchants,setMerchants]=useState<Merchant[]>([]);
  const [q,setQ]=useState("");
  const [query,setQuery]=useState("");
  const [page,setPage]=useState(1);
  const [total,setTotal]=useState(0);
  const [editing,setEditing]=useState<number|null>(null);
  const [form,setForm]=useState<FormShape>(emptyForm());
  const [showForm,setShowForm]=useState(false);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try{
      const params=new URLSearchParams({page:String(page),limit:"20"});
      if(query)params.set("q",query);
      const result=await request<{items:RecordItem[];total:number}>(`/workspace/${kind}?${params}`);
      setItems(result.items||[]);setTotal(result.total||0);
    }catch(e){setError((e as Error).message);setItems([]);}
    finally{setLoading(false);}
  },[kind,query,page]);

  useEffect(()=>{load();},[load]);
  useEffect(()=>{
    if(!canWrite)return;
    request<{items:Merchant[]}>("/merchants?limit=100")
      .then(res=>setMerchants(res.items||[])).catch(()=>setMerchants([]));
  },[canWrite]);

  function startCreate(){setEditing(null);setForm(emptyForm());setShowForm(true);setError("");setNotice("");}
  function startEdit(item:RecordItem){
    setEditing(item.id);
    setForm({title:item.title,body:item.body,status:item.status,merchant_id:item.merchant_id?String(item.merchant_id):""});
    setShowForm(true);setError("");setNotice("");
  }
  async function save(e:FormEvent){
    e.preventDefault();
    if(!canWrite)return;
    setBusy(true);setError("");setNotice("");
    try{
      const payload:Record<string,unknown>={title:form.title.trim(),body:form.body,status:form.status};
      if(editing===null)payload.merchant_id=form.merchant_id?Number(form.merchant_id):null;
      const path=editing===null?`/workspace/${kind}`:`/workspace/${kind}/${editing}`;
      await request(path,{method:editing===null?"POST":"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      setShowForm(false);setEditing(null);setForm(emptyForm());setNotice("资料已保存");
      await load();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  async function remove(item:RecordItem){
    if(!canWrite||!window.confirm(`确定删除「${item.title}」？删除后不可恢复。`))return;
    setBusy(true);setError("");setNotice("");
    try{
      await request(`/workspace/${kind}/${item.id}`,{method:"DELETE"});
      setNotice("资料已删除");
      if(items.length===1&&page>1)setPage(page-1);
      else await load();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  const pages=Math.max(1,Math.ceil(total/20));

  return <div className="v20-integrated">
    <div className="heading order-heading">
      <div><h1>{label}</h1><p>支持搜索、创建、编辑和归档资料，按当前账号权限保存。</p></div>
      {canWrite&&<button className="primary" onClick={startCreate}>＋ 新建资料</button>}
    </div>
    {error&&<div className="error" role="alert">{error}</div>}
    {notice&&<div className="success">{notice}</div>}
    <div className="panel">
      <form className="toolbar bm-ws-toolbar" onSubmit={e=>{e.preventDefault();setPage(1);setQuery(q.trim());}}>
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder={`搜索${label}名称`}/>
        <button className="secondary-btn">搜索</button>
        <button type="button" className="secondary-btn" onClick={()=>load()}>刷新</button>
      </form>
      {loading?<p className="empty">正在加载资料…</p>:
       items.length===0?<div className="empty">暂无资料。{canWrite?"点击「新建资料」开始添加。":""}</div>:
       <div className="bm-ws-list">{items.map(item=><article className="bm-ws-item" key={item.id}>
         <div><div className="bm-ws-title"><strong>{item.title}</strong><span className="order-chip">{item.status==="active"?"进行中":item.status==="archived"?"已归档":"草稿"}</span></div>
           {item.body&&<p className="bm-ws-description">{item.body}</p>}
           <small className="muted">#{item.id} {item.merchant_id?` · 商家 #${item.merchant_id}`:""} · {item.updated_at||item.created_at}</small>
         </div>
         {canWrite&&<div className="bm-ws-actions"><button className="secondary-btn" onClick={()=>startEdit(item)}>编辑</button><button className="textbtn danger" disabled={busy} onClick={()=>remove(item)}>删除</button></div>}
       </article>)}</div>}
      {total>20&&<div className="pager"><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>上一页</button><span>第 {page} / {pages} 页 · 共 {total} 条</span><button disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>下一页</button></div>}
    </div>
    {showForm&&canWrite&&<div className="modal-bg" onClick={()=>setShowForm(false)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><h3>{editing===null?"新建资料":"编辑资料"}</h3><button onClick={()=>setShowForm(false)}>关闭</button></div>
      <form className="order-form" onSubmit={save}>
        <label className="span2">名称<input required maxLength={200} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
        <label className="span2">内容说明<textarea rows={7} maxLength={20000} value={form.body} onChange={e=>setForm({...form,body:e.target.value})}/></label>
        <label>状态<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option value="draft">草稿</option><option value="active">进行中</option><option value="archived">已归档</option></select></label>
        {editing===null&&<label>关联商家（可选）<select value={form.merchant_id} onChange={e=>setForm({...form,merchant_id:e.target.value})}><option value="">团队共享资料</option>{merchants.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>}
        <div className="order-modal-actions span2"><button type="button" className="secondary-btn" onClick={()=>setShowForm(false)}>取消</button><button className="primary" disabled={busy}>{busy?"保存中…":"保存资料"}</button></div>
      </form>
    </div></div>}
  </div>;
}
