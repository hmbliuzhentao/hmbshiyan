"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";

type User = { id: number; name: string; role: string };
type OrderStatus = "confirmed" | "in_progress" | "delivered" | "closed" | "cancelled";
type Order = {
  merchant_id: number | null; id: number; order_no: string; client_name: string; contact: string; title: string; service_type: string;
  owner_id: number | null; owner_name: string; amount_cents: number; cost_cents: number; paid_cents: number;
  outstanding_cents: number; estimated_profit_cents: number; status: OrderStatus; order_date: string;
  due_date: string | null; notes: string; created_at: string;
};
type Payment = { id: number; amount_cents: number; received_on: string; method: string; remark: string; is_void: boolean };
type OrderDetail = Order & { payments: Payment[]; history: {id:number; action:string; detail:string; created_at:string}[] };
type Stats = { order_count:number; cancelled_count:number; contract_cents:number; cost_cents:number;
  estimated_profit_cents:number; received_cents:number; outstanding_cents:number; overdue_count:number;
  status_counts:Record<string,number>; monthly_receipts:{month:string;received_cents:number}[] };

const statuses: {value: OrderStatus; label:string}[] = [
  {value:"confirmed",label:"已确认"}, {value:"in_progress",label:"制作中"}, {value:"delivered",label:"已交付"},
  {value:"closed",label:"已结单"}, {value:"cancelled",label:"已取消"}
];
const statusName = (s:string) => statuses.find(x => x.value===s)?.label || s;
const money = (n:number) => (n/100).toLocaleString("zh-CN",{style:"currency",currency:"CNY"});
const today = () => new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
const nowDate = (s:string) => s?.slice(0,10) || "";
const initial = () => ({client_name:"",contact:"",title:"",service_type:"视频剪辑",owner_id:"",merchant_id:"",
  amount:"0.00",cost:"0.00",status:"confirmed" as OrderStatus,order_date:today(),due_date:"",notes:""});
type FormData = ReturnType<typeof initial>;

async function get<T>(route:string, init?:RequestInit):Promise<T> {
  const response = await fetch(`/api${route}`, {credentials:"include",...init});
  if (!response.ok) {
    const problem = await response.json().catch(()=>null);
    const detail = problem?.detail;
    throw Error(typeof detail === "string" ? detail : `操作失败（HTTP ${response.status}）`);
  }
  return response.json();
}

export function OrdersSummary({ onOpen }:{onOpen:()=>void}) {
  const [stats,setStats] = useState<Stats|null>(null);
  useEffect(()=>{get<Stats>("/orders/stats").then(setStats).catch(()=>{});},[]);
  if (!stats) return null;
  return <div className="panel order-dashboard-preview"><div className="order-inline"><div><h3>接单业务概况</h3><p className="muted">来自订单台账的真实数据（不含已取消订单）</p></div><button className="primary" onClick={onOpen}>进入订单管理</button></div>
    <div className="order-metrics-mini"><div>订单数量<strong>{stats.order_count}</strong></div><div>订单总额<strong>{money(stats.contract_cents)}</strong></div><div>已收款<strong>{money(stats.received_cents)}</strong></div><div>待收款<strong>{money(stats.outstanding_cents)}</strong></div></div>
  </div>;
}

export default function OrdersPanel({user}:{user:User}) {
  const canEdit = user.role==="admin";
  const [list,setList] = useState<Order[]>([]);
  const [stats,setStats] = useState<Stats|null>(null);
  const [owners,setOwners] = useState<User[]>([]);
  const [merchants,setMerchants] = useState<{id:number;name:string;status:string}[]>([]);
  const [total,setTotal] = useState(0);
  const [page,setPage] = useState(1);
  const [query,setQuery] = useState(""); const [status,setStatus] = useState("");
  const [fromDate,setFromDate] = useState("");const [toDate,setToDate] = useState("");
  const [search,setSearch] = useState({q:"",status:"",from:"",to:""});
  const [editing,setEditing] = useState<null|"new"|number>(null);
  const [form,setForm] = useState<FormData>(initial());
  const [detail,setDetail] = useState<OrderDetail|null>(null);
  const [payment,setPayment] = useState({amount:"",received_on:today(),method:"银行转账",remark:""});
  const [busy,setBusy] = useState(false); const [error,setError] = useState(""); const [ok,setOk] = useState("");

  const queryParams = useCallback((withPage=true)=>{
    const params = new URLSearchParams();
    if (withPage) {params.set("page",String(page));params.set("limit","20");}
    if(search.q) params.set("q",search.q);
    if(search.status) params.set("status",search.status);
    if(search.from) params.set("from_date",search.from);
    if(search.to) params.set("to_date",search.to);
    return params.toString();
  },[page,search]);
  const refresh = useCallback(async()=>{
    const [orders,summary] = await Promise.all([
      get<{items:Order[];total:number}>(`/orders?${queryParams()}`),
      get<Stats>(`/orders/stats?${new URLSearchParams([...(search.from?[["from_date",search.from] as [string,string]]:[]),...(search.to?[["to_date",search.to] as [string,string]]:[])])}`)
    ]);
    setList(orders.items);setTotal(orders.total);setStats(summary);
  },[queryParams,search.from,search.to]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
  useEffect(()=>{if(canEdit){
    get<User[]>("/users").then(setOwners).catch(()=>{});
    get<{items:{id:number;name:string;status:string}[]}>("/merchants?status=approved&limit=100").then(r=>setMerchants(r.items)).catch(()=>{});
  }},[canEdit]);
  const loadDetail = async (id:number) => setDetail(await get<OrderDetail>(`/orders/${id}`));
  const openDetail = async (id:number) => {setError("");setOk(""); try{await loadDetail(id);}catch(e){setError((e as Error).message);}};
  const startCreate = () => {setEditing("new");setDetail(null);setForm(initial());setError("");setOk("");};
  const startEdit = (o:OrderDetail) => {
    setForm({client_name:o.client_name,contact:o.contact,title:o.title,service_type:o.service_type,
      owner_id:o.owner_id===null?"":String(o.owner_id),merchant_id:o.merchant_id===null?"":String(o.merchant_id),amount:(o.amount_cents/100).toFixed(2),
      cost:(o.cost_cents/100).toFixed(2),status:o.status,order_date:o.order_date,
      due_date:o.due_date||"",notes:o.notes});setEditing(o.id);setError("");setOk("");
  };
  const change = (name:keyof FormData,value:string) => setForm(s=>({...s,[name]:value}));

  const submit = async (e:FormEvent) => {
    e.preventDefault();setBusy(true);setError("");setOk("");
    try {
      const payload = {...form,amount:form.amount,cost:form.cost,owner_id:form.owner_id?Number(form.owner_id):null,merchant_id:form.merchant_id?Number(form.merchant_id):null,
        due_date:form.due_date||null};
      if(editing==="new") await get<Order>("/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      else await get<Order>(`/orders/${editing}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      const target = editing; setEditing(null);setPage(1);setOk("订单保存成功");await refresh();
      if(typeof target==="number") await loadDetail(target);
    } catch(e){setError((e as Error).message);} finally{setBusy(false);}
  };
  const addPayment=async(e:FormEvent)=>{
    e.preventDefault(); if(!detail)return;setBusy(true);setError("");
    try{
      await get(`/orders/${detail.id}/payments`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payment)});
      await loadDetail(detail.id);await refresh();setPayment({amount:"",received_on:today(),method:"银行转账",remark:""});setOk("收款记录已保存");
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  };
  const voidPayment=async(p:Payment)=>{
    if(!detail||!confirm(`确认将 ${money(p.amount_cents)} 的收款记录作废？此操作会保留审计记录。`))return;
    setBusy(true);setError("");try{await get(`/orders/${detail.id}/payments/${p.id}/void`,{method:"POST"});await loadDetail(detail.id);await refresh();setOk("收款记录已作废");}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  };
  const exportCsv=async()=>{
    setError("");try{
      const res=await fetch(`/api/orders/export?${queryParams(false)}`,{credentials:"include"});
      if(!res.ok)throw Error("导出失败");
      const url=URL.createObjectURL(await res.blob());const a=document.createElement("a");
      a.href=url;a.download=`订单台账-${today()}.csv`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    }catch(e){setError((e as Error).message);}
  };

  return <div className="orders-root">
    <div className="heading order-heading"><div><h1>接单业务管理</h1><p>订单台账 · 客户 · 项目进度 · 收款及业绩统计</p></div>
      <div className="order-actions">{canEdit&&<><button className="secondary-btn" onClick={exportCsv}>↓ 导出 CSV</button><button className="primary" onClick={startCreate}>＋ 新建订单</button></>}</div>
    </div>
    {error&&<div className="error">{error}<button className="textbtn" onClick={()=>setError("")}>关闭</button></div>}
    {ok&&<div className="success">{ok}</div>}
    <div className="order-metrics">
      {[
        {label:"有效订单",value:stats?String(stats.order_count):"—",sub:"不含取消单"},
        {label:"接单总金额",value:stats?money(stats.contract_cents):"—",sub:"签约/约定金额"},
        {label:"实际已收款",value:stats?money(stats.received_cents):"—",sub:"有效收款合计"},
        {label:"待收款",value:stats?money(stats.outstanding_cents):"—",sub:"订单金额 - 已收"},
        {label:"预估毛利",value:stats?money(stats.estimated_profit_cents):"—",sub:"订单金额 - 预计成本"},
        {label:"逾期未交付",value:stats?String(stats.overdue_count):"—",sub:"根据计划交付日"}
      ].map(m=><div className="panel order-metric" key={m.label}><span>{m.label}</span><strong>{m.value}</strong><small>{m.sub}</small></div>)}
    </div>
    <div className="order-panels">
      <div className="panel"><h3>近六个月收款趋势</h3><div className="order-bars">{(stats?.monthly_receipts||[]).map(m=><div className="order-bar-col" key={m.month}><strong>{money(m.received_cents)}</strong><div className="order-bar" style={{height:`${Math.max(6,m.received_cents/Math.max(1,...(stats?.monthly_receipts||[]).map(x=>x.received_cents))*116)}px`}}/><small>{m.month.slice(5)}月</small></div>)}</div><p className="muted order-small">按实际收款日期统计，不按接单日期计算</p></div>
      <div className="panel"><h3>订单进度分布</h3><div className="order-status-list">{statuses.map(s=><div key={s.value}><span>{s.label}</span><strong>{stats?.status_counts[s.value]||0} 单</strong></div>)}</div><p className="muted order-small">取消订单不计入金额统计</p></div>
    </div>
    <div className="panel order-filter">
      <form onSubmit={e=>{e.preventDefault();setPage(1);setSearch({q:query,status,from:fromDate,to:toDate});}}>
        <input placeholder="订单号 / 客户 / 项目 / 类型" value={query} onChange={e=>setQuery(e.target.value)} />
        <select value={status} onChange={e=>setStatus(e.target.value)}><option value="">全部状态</option>{statuses.map(s=><option key={s.value} value={s.value}>{s.label}</option>)}</select>
        <label>从 <input type="date" value={fromDate} onChange={e=>setFromDate(e.target.value)}/></label>
        <label>至 <input type="date" value={toDate} onChange={e=>setToDate(e.target.value)}/></label>
        <button className="primary">筛选</button>
        <button type="button" className="secondary-btn" onClick={()=>{setQuery("");setStatus("");setFromDate("");setToDate("");setPage(1);setSearch({q:"",status:"",from:"",to:""});}}>重置</button>
      </form>
    </div>
    <div className="panel tablewrap"><table><thead><tr><th>订单编号 / 接单日期</th><th>客户与项目</th><th>负责人</th><th>订单金额</th><th>已收 / 待收</th><th>状态</th><th>计划交付</th><th>操作</th></tr></thead><tbody>
      {list.map(o=><tr key={o.id}><td><strong>{o.order_no}</strong><div className="muted">{o.order_date}</div></td><td><strong>{o.client_name}</strong><div className="muted">{o.title}</div><small>{o.service_type}</small></td><td>{o.owner_name||"—"}</td><td>{money(o.amount_cents)}</td><td><span className="order-paid">{money(o.paid_cents)}</span><div className="muted">待收 {money(o.outstanding_cents)}</div></td><td><span className={`order-chip ${o.status}`}>{statusName(o.status)}</span></td><td>{o.due_date||"—"}</td><td><button className="textbtn" onClick={()=>openDetail(o.id)}>详情 / 收款</button></td></tr>)}
      {!list.length&&<tr><td colSpan={8} className="empty">还没有符合条件的订单，点击“新建订单”开始记录</td></tr>}
    </tbody></table></div>
    <div className="pager"><span>共 {total} 条</span><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>上一页</button><span>第 {page} 页</span><button disabled={page*20>=total} onClick={()=>setPage(p=>p+1)}>下一页</button></div>
    <p className="muted order-small">普通用户只可查看；管理员可以创建、修改订单及登记收款。导出数据中包含客户资料，请妥善保管。</p>

    {editing!==null&&<div className="modal-bg" onClick={()=>setEditing(null)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><h3>{editing==="new"?"新建接单记录":"编辑订单"}</h3><button onClick={()=>setEditing(null)}>✕</button></div>
      <form onSubmit={submit} className="order-form">
        <label>客户名称 *<input required maxLength={120} value={form.client_name} onChange={e=>change("client_name",e.target.value)}/></label>
        <label>关联商家<select value={form.merchant_id} onChange={e=>change("merchant_id",e.target.value)}><option value="">未关联（仅内部可见）</option>{merchants.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        <label>客户联系方式<input maxLength={120} value={form.contact} onChange={e=>change("contact",e.target.value)}/></label>
        <label className="span2">项目名称 *<input required maxLength={200} value={form.title} onChange={e=>change("title",e.target.value)}/></label>
        <label>业务类型 *<input required maxLength={80} list="types" value={form.service_type} onChange={e=>change("service_type",e.target.value)}/><datalist id="types"><option value="视频剪辑"/><option value="短视频制作"/><option value="拍摄服务"/><option value="账号运营"/><option value="广告投放"/><option value="素材整理"/><option value="其他"/></datalist></label>
        <label>负责人<select value={form.owner_id} onChange={e=>change("owner_id",e.target.value)}><option value="">未分配</option>{owners.map(o=><option value={o.id} key={o.id}>{o.name}</option>)}</select></label>
        <label>订单金额（元）*<input type="number" min="0" step="0.01" required value={form.amount} onChange={e=>change("amount",e.target.value)}/></label>
        <label>预估成本（元）*<input type="number" min="0" step="0.01" required value={form.cost} onChange={e=>change("cost",e.target.value)}/></label>
        <label>接单日期<input type="date" required value={form.order_date} onChange={e=>change("order_date",e.target.value)}/></label>
        <label>计划交付日<input type="date" value={form.due_date} onChange={e=>change("due_date",e.target.value)}/></label>
        <label>订单状态<select value={form.status} onChange={e=>change("status",e.target.value)}>{statuses.map(s=><option key={s.value} value={s.value}>{s.label}</option>)}</select></label>
        <label className="span2">备注<textarea rows={3} maxLength={2000} value={form.notes} onChange={e=>change("notes",e.target.value)}/></label>
        <div className="span2 order-modal-actions"><button type="button" className="secondary-btn" onClick={()=>setEditing(null)}>取消</button><button disabled={busy} className="primary">{busy?"保存中…":"保存订单"}</button></div>
      </form>
    </div></div>}

    {detail&&editing===null&&<div className="modal-bg" onClick={()=>setDetail(null)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><div><h3>订单 {detail.order_no}</h3><p className="muted">{detail.client_name} · {detail.title}</p></div><button onClick={()=>setDetail(null)}>✕</button></div>
      <div className="order-detail-metrics"><div>订单总额<strong>{money(detail.amount_cents)}</strong></div><div>已收款<strong>{money(detail.paid_cents)}</strong></div><div>待收款<strong>{money(detail.outstanding_cents)}</strong></div><div>预估毛利<strong>{money(detail.estimated_profit_cents)}</strong></div></div>
      <div className="order-detail-row"><span>负责人：{detail.owner_name||"未分配"}</span><span>交付日期：{detail.due_date||"未设置"}</span><span>状态：{statusName(detail.status)}</span></div>
      {detail.notes&&<p className="order-notes">备注：{detail.notes}</p>}
      {canEdit&&<button className="secondary-btn" onClick={()=>startEdit(detail)}>编辑订单信息</button>}
      <h3 className="order-subheading">收款明细</h3>
      <div className="tablewrap"><table><thead><tr><th>日期</th><th>金额</th><th>方式</th><th>备注</th><th>状态</th></tr></thead><tbody>{detail.payments.map(p=><tr key={p.id}><td>{p.received_on}</td><td>{money(p.amount_cents)}</td><td>{p.method}</td><td>{p.remark||"—"}</td><td>{p.is_void?"已作废":canEdit?<button className="textbtn danger" disabled={busy} onClick={()=>voidPayment(p)}>作废</button>:"有效"}</td></tr>)}{!detail.payments.length&&<tr><td className="empty" colSpan={5}>尚无收款记录</td></tr>}</tbody></table></div>
      {canEdit&&detail.status!=="cancelled"&&detail.outstanding_cents>0&&<form className="order-payment" onSubmit={addPayment}><h3>登记新收款</h3><div className="order-form"><label>本次收款（元）<input type="number" min="0.01" max={(detail.outstanding_cents/100).toFixed(2)} step="0.01" value={payment.amount} required onChange={e=>setPayment({...payment,amount:e.target.value})}/></label><label>到账日期<input type="date" required value={payment.received_on} onChange={e=>setPayment({...payment,received_on:e.target.value})}/></label><label>收款方式<select value={payment.method} onChange={e=>setPayment({...payment,method:e.target.value})}><option>银行转账</option><option>支付宝</option><option>微信支付</option><option>现金</option><option>其他</option></select></label><label>备注<input maxLength={300} value={payment.remark} onChange={e=>setPayment({...payment,remark:e.target.value})}/></label></div><button disabled={busy} className="primary">{busy?"提交中…":"保存收款记录"}</button></form>}
      <h3 className="order-subheading">操作记录</h3><div className="order-history">{detail.history.map(x=><div key={x.id}><span>{x.detail}</span><small>{x.created_at?.replace("T"," ").slice(0,19)}</small></div>)}</div>
    </div></div>}
  </div>;
}
