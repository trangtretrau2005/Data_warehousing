const el=id=>document.getElementById(id);
const fmt=n=>n.toLocaleString('vi-VN',{maximumFractionDigits:2});
const sign=n=>n>0?'+'+fmt(n):fmt(n);
const period=m=>m.slice(0,4)+'-Q'+Math.ceil(Number(m.slice(5,7))/3);
const monthName=m=>m.slice(5,7)+'/'+m.slice(0,4);
const quarterName=q=>'Quý '+q.slice(-1)+' / '+q.slice(0,4);
let data, market, quarter;
const path=[];
function groups(rows,key){
 const result=new Map();
 for(const row of rows){
  const name=key(row);
  if(!result.has(name))result.set(name,{name,sales:0,budget:0,rows:[]});
  const g=result.get(name);g.sales+=row.Sales;g.budget+=row.BudgetSales;g.rows.push(row);
 }
 return [...result.values()].map(g=>({...g,gap:g.sales-g.budget}));
}
function append(parent,tag,text,cls){
 const node=document.createElement(tag);if(cls)node.className=cls;
 node.textContent=text;parent.append(node);return node;
}
function draw(){
 const rows=data.productPeriod.filter(r=>r.Market===market&&period(r.MonthStart)===quarter);
 const panel=el('levels');panel.replaceChildren();
 const total=groups(rows,()=>market)[0];
 el('results').hidden=!total;
 el('status').textContent=total?'':'Không có bản ghi trong phạm vi đã chọn.';
 if(!total)return;
 el('scope').textContent=market+' · '+quarterName(quarter);
 el('headline').textContent=total.gap===0?'Vừa đủ kế hoạch':(total.gap<0?'Hụt ':'Vượt ')+fmt(Math.abs(total.gap))+' so với kế hoạch';
 el('sales').textContent=fmt(total.sales);el('budget').textContent=fmt(total.budget);
 const levels=[['Tháng',r=>r.MonthStart],['Nhóm sản phẩm',r=>data.meta.productTypes[r.ProductName]],['Sản phẩm',r=>r.ProductName]];
 let parent=total;
 levels.forEach(([title,key],depth)=>{
  const children=groups(parent.rows,key);
  children.sort((a,b)=>depth===0?a.name.localeCompare(b.name):a.gap-b.gap||a.name.localeCompare(b.name));
  const preferred=children.reduce((a,b)=>a.gap<=b.gap?a:b);
  const chosen=children.find(c=>c.name===path[depth])||preferred;
  path[depth]=chosen.name;
  if(depth===0)el('story').textContent=preferred.gap<0?'Tháng hụt nhiều nhất: '+monthName(preferred.name)+' ('+sign(preferred.gap)+').':'Mọi tháng có dữ liệu đều đạt hoặc vượt kế hoạch.';
  const box=append(panel,'section','','level');
  append(box,'h3',title);append(box,'p',(depth===0?quarterName(quarter):depth===1?monthName(path[0]):path[1])+' · Tổng '+sign(parent.gap));
  const scale=Math.max(1,...children.map(c=>Math.abs(c.gap)));
  for(const child of children){
   const button=append(box,'button','','branch');
   button.setAttribute('aria-pressed',String(child===chosen));
   const row=append(button,'span','','row');append(row,'span',depth===0?monthName(child.name):child.name);append(row,'b',sign(child.gap));
   const track=append(button,'span','','track'),bar=append(track,'i','',child.gap<0?'neg':'pos');
   bar.style[child.gap<0?'right':'left']='50%';bar.style.width=(49*Math.abs(child.gap)/scale)+'%';
   button.onclick=()=>{path.splice(depth,path.length-depth,child.name);draw();panel.children[depth].querySelector('[aria-pressed=true]').focus();};
  }
  parent=chosen;
 });
 el('leaf').textContent=path[2];
 el('formula').textContent=monthName(path[0])+' · '+market+' · '+path[1]+' | Sales '+fmt(parent.sales)+' − ngân sách '+fmt(parent.budget)+' = '+sign(parent.gap);
 el('cube').href='/#'+new URLSearchParams({month:path[0],market,product:path[2]});
 el('source').textContent=data.meta.sourceLabel+' · Chênh lệch = tổng Sales − tổng BudgetSales. Mỗi biểu đồ có cùng mốc 0 và thang đo riêng cho các nhánh cùng cấp.';
}
function apply(){
 market=el('market').value;quarter=el('quarter').value;path.length=0;draw();
}
el('filters').onsubmit=e=>{e.preventDefault();apply();};
async function init(){
 try{
  const response=await fetch('/api/data');if(!response.ok)throw Error();
  data=await response.json();
  const quarters=[...new Set(data.meta.months.map(period))].sort();
  for(const m of data.meta.markets)el('market').add(new Option(m,m));
  for(const q of quarters)el('quarter').add(new Option(quarterName(q),q));
  el('market').value=data.meta.markets.includes('South')?'South':data.meta.markets[0];
  el('quarter').value=quarters.includes('2013-Q3')?'2013-Q3':quarters.at(-1);
  for(const id of ['market','quarter','submit'])el(id).disabled=false;
  for(const id of ['market','quarter'])el(id).onchange=apply;
  apply();
 }catch{el('status').textContent='Chưa đọc được dữ liệu kho. Hãy tải lại trang.';}
}
init();
