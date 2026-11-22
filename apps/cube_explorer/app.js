import {CubeScene} from './cube.js';

const $ = id => document.getElementById(id);
const number = new Intl.NumberFormat('vi-VN',{maximumFractionDigits:0});
const percent = new Intl.NumberFormat('vi-VN',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1});
const fmt = value => value===null||!Number.isFinite(value)?'—':number.format(value);
const signed = value => `${value>0?'+':''}${fmt(value)}`;
const monthName = month => `${month.slice(5,7)}/${month.slice(0,4)}`;
const escapeHTML = text => String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const moneyFields = ['Sales','BudgetSales','Profit','Gap'];

let payload;
let scene;
let months=[];
let cubeRows=[];
let requestId=0;
let toastTimer;
const state={year:'2013',month:'2013-08-01',market:'',product:'',level:'type',measure:'Gap',mode:'all',pivot:false,view:'explore'};

function sumRows(rows){
  if(!rows.length)return null;
  return rows.reduce((acc,row)=>{for(const key of moneyFields)acc[key]+=Number(row[key]);return acc;},{Sales:0,BudgetSales:0,Profit:0,Gap:0});
}

function groupRows(rows, keyOf){
  const groups=new Map();
  rows.forEach(row=>{
    const key=keyOf(row);
    if(!groups.has(key))groups.set(key,{...row,Sales:0,BudgetSales:0,Profit:0,Gap:0});
    const group=groups.get(key);
    for(const field of moneyFields)group[field]+=Number(row[field]);
  });
  return [...groups.values()];
}

function productOf(row){return state.level==='type'?payload.meta.productTypes[row.ProductName]:row.ProductName;}
function filteredRows({market=state.market,month=state.month,product=state.product}={}){
  return payload.productPeriod.filter(row=>row.MonthStart===month&&(!market||row.Market===market)&&(!product||productOf(row)===product));
}

function toast(text){
  $('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true;},4200);
}

function showError(message){$('error-banner').textContent=message;$('error-banner').hidden=false;}
document.addEventListener('cube-error',event=>showError(event.detail));

function selectOptions(select, options, selected){
  select.replaceChildren(...options.map(({value,label})=>{const option=document.createElement('option');option.value=value;option.textContent=label;return option;}));
  select.value=selected;select.disabled=false;
}

function prepareOptions(){
  const years=[...new Set(payload.meta.months.map(month=>month.slice(0,4)))];
  if(!years.includes(state.year)&&state.year!=='all')state.year=years.at(-1);
  selectOptions($('year-select'),[...years.map(year=>({value:year,label:`Năm ${year}`})),{value:'all',label:`Toàn bộ ${payload.meta.months.length} tháng`}],state.year);
  selectOptions($('market-select'),[{value:'',label:'Tất cả thị trường'},...payload.meta.markets.map(market=>({value:market,label:market}))],state.market);
  syncProductOptions();
}

function syncProductOptions(){
  const names=state.level==='type'?[...new Set(Object.values(payload.meta.productTypes))].sort():payload.meta.products;
  if(state.product&&!names.includes(state.product))state.product='';
  selectOptions($('product-select'),[{value:'',label:state.level==='type'?'Tất cả nhóm sản phẩm':'Tất cả sản phẩm'},...names.map(name=>({value:name,label:name}))],state.product);
  document.querySelector('label[for="product-select"]').textContent=state.level==='type'?'Nhóm sản phẩm':'Sản phẩm';
}

function syncAnalysisFilters(){
  $('analysis-level-select').value=state.level;
  selectOptions($('analysis-month-select'),payload.meta.months.map(month=>({value:month,label:monthName(month)})),state.month);
  selectOptions($('analysis-market-select'),[{value:'',label:'Tất cả thị trường'},...payload.meta.markets.map(market=>({value:market,label:market}))],state.market);
  const names=state.level==='type'?[...new Set(Object.values(payload.meta.productTypes))].sort():payload.meta.products;
  selectOptions($('analysis-product-select'),[{value:'',label:'Tất cả sản phẩm'},...names.map(name=>({value:name,label:name}))],state.product);
  $('filter-summary').textContent=`${monthName(state.month)} · ${state.market||'Tất cả thị trường'}`;
}

function rebuildCube(){
  months=payload.meta.months.filter(month=>state.year==='all'||month.startsWith(state.year));
  if(!months.includes(state.month))state.month=months[0];
  const rows=payload.productPeriod.filter(row=>months.includes(row.MonthStart)).map(row=>({...row,Product:productOf(row)}));
  cubeRows=groupRows(rows,row=>`${row.MonthStart}|${row.Market}|${row.Product}`);
  const products=[...new Set(cubeRows.map(row=>row.Product))].sort();
  scene.setData(cubeRows,{...state},months,payload.meta.markets,products);
  $('cube-grain').textContent=`THÁNG × MARKET × ${state.level==='type'?'NHÓM':'PRODUCT'}`;
  const titles={all:'Nhìn toàn khối',slice:`Một lát tháng ${monthName(state.month)}`,explode:'Tách từng lớp thời gian'};
  $('cube-title').textContent=titles[state.mode];
  $('month-label').textContent=monthName(state.month).replace('/',' / ');
  $('month-slider').max=months.length-1;$('month-slider').value=months.indexOf(state.month);
  $('time-start').textContent=monthName(months[0]);$('time-end').textContent=monthName(months.at(-1));
  $('prev-month').disabled=months.indexOf(state.month)===0;$('next-month').disabled=months.indexOf(state.month)===months.length-1;
  let visible=cubeRows.length;
  if(state.mode==='slice')visible=cubeRows.filter(row=>row.MonthStart===state.month&&(!state.market||row.Market===state.market)&&(!state.product||row.Product===state.product)).length;
  $('visible-cells').textContent=`${fmt(visible)} ô ${state.mode==='slice'?'trong lát':'dữ liệu'}`;
  if(state.measure==='Gap'){
    $('legend-negative').textContent='Hụt kế hoạch';$('legend-positive').textContent='Vượt kế hoạch';
    $('color-scale').style.background='linear-gradient(90deg,#e48485,#bcc8e8,#64cfbc)';
  }else{
    const values=cubeRows.map(row=>row[state.measure]),min=Math.min(...values),max=Math.max(...values);
    $('legend-negative').textContent=`Thấp ${fmt(min)}`;$('legend-positive').textContent=`Cao ${fmt(max)}`;
    $('color-scale').style.background=min<0?'linear-gradient(90deg,#e48485,#bcc8e8,#64cfbc)':'linear-gradient(90deg,#c4cef6,#7a9be6)';
  }
  for(const button of $('view-control').querySelectorAll('button')){const active=button.dataset.mode===state.mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',active);}
  for(const button of $('level-control').querySelectorAll('button')){const active=button.dataset.level===state.level;button.classList.toggle('active',active);button.setAttribute('aria-pressed',active);}
  $('pivot-button').setAttribute('aria-pressed',String(state.pivot));
}

function updateKpis(){
  const rows=filteredRows();
  const marketRows=payload.marketPeriod.filter(row=>row.MonthStart===state.month&&(!state.market||row.Market===state.market));
  const total=state.product?sumRows(rows):sumRows(marketRows);
  $('scope-market').textContent=state.market||'Toàn chuỗi';$('scope-month').textContent=monthName(state.month);
  $('kpi-sales').textContent=fmt(total?.Sales??null);$('kpi-budget').textContent=fmt(total?.BudgetSales??null);$('kpi-gap').textContent=total?signed(total.Gap):'—';
  $('kpi-gap').className=total?.Gap<0?'negative':'positive';
  const ratio=total&&total.BudgetSales!==0?total.Sales/total.BudgetSales:null;
  $('kpi-ratio').textContent=ratio===null?'—':percent.format(ratio);
  $('analysis-sales').textContent=fmt(total?.Sales??null);
  $('analysis-budget').textContent=fmt(total?.BudgetSales??null);
  $('analysis-gap').textContent=total?signed(total.Gap):'—';
  $('analysis-gap').className=total?.Gap<0?'negative':'positive';
  $('analysis-ratio').textContent=ratio===null?'—':percent.format(ratio);
  $('analysis-scope').textContent=`${monthName(state.month)} · ${state.market||'Toàn chuỗi'} · ${state.product||'Tất cả sản phẩm'}. Bộ lọc được giữ khi chuyển tab.`;
  $('achievement-fill').style.width=`${ratio===null?0:Math.max(0,Math.min(ratio/1.2,1))*100}%`;
  $('achievement-fill').style.background=total?.Gap<0?'#e38c89':'#64baa8';
  const subject=state.product?`${state.product} · ${state.market||'toàn chuỗi'}`:state.market||'Toàn chuỗi';
  $('scope-sentence').textContent=!total?`${subject}: không có bản ghi ở tháng này. Ô thiếu không được đổi thành 0.`:`${subject} ${total.Gap<0?'hụt':'vượt'} ${fmt(Math.abs(total.Gap))} so với ngân sách cùng kỳ.`;
  const chosen=Boolean(state.product);
  $('selected-cell').hidden=!chosen;$('clear-product').hidden=!chosen;
  if(chosen){
    $('cell-title').textContent=state.product;
    $('cell-values').textContent=total?`Sales ${fmt(total.Sales)} · Budget ${fmt(total.BudgetSales)} · Profit ${fmt(total.Profit)}`:'Tổ hợp này không có bản ghi trong mart.';
  }
  const baseline=payload.marketPeriod.filter(row=>row.MonthStart===state.month&&(!state.market||row.Market===state.market));
  const baselineTotal=sumRows(baseline),fromProducts=sumRows(filteredRows({product:''}));
  const match=Boolean(baselineTotal&&fromProducts&&moneyFields.every(key=>Math.abs(baselineTotal[key]-fromProducts[key])<.01));
  $('reconcile-text').textContent=match?'Tổng các sản phẩm khớp mart tháng–Market.':'Không đủ ô để đối chiếu tổng các cấp.';
  $('lineage-month').textContent=monthName(state.month);$('lineage-market').textContent=state.market||'Tất cả thị trường';$('lineage-product').textContent=state.product||'Tất cả sản phẩm';
  $('lineage-sales').textContent=fmt(total?.Sales??null);$('lineage-budget').textContent=fmt(total?.BudgetSales??null);$('lineage-profit').textContent=fmt(total?.Profit??null);
}

function updateRanking(){
  const rows=filteredRows({product:''});
  const grouped=groupRows(rows.map(row=>({...row,Product:productOf(row)})),row=>row.Product).sort((a,b)=>a.Gap-b.Gap||a.Product.localeCompare(b.Product));
  $('ranking-title').textContent=state.level==='type'?'Nhóm sản phẩm cần xem':'Sản phẩm cần xem';
  const max=Math.max(...grouped.map(row=>Math.abs(row.Gap)),1);
  $('product-ranking').replaceChildren();
  const shown=grouped.slice(0,state.level==='type'?4:5);
  if(state.product&&!shown.some(row=>row.Product===state.product)){
    const selected=grouped.find(row=>row.Product===state.product);if(selected)shown.push(selected);
  }
  for(const row of shown){
    const button=document.createElement('button');button.className=`rank-row ${row.Gap<0?'neg':''} ${row.Product===state.product?'selected':''}`;
    button.setAttribute('aria-label',`${row.Product}, Gap ${signed(row.Gap)}. Xem chi tiết`);
    button.innerHTML=`<div><span>${escapeHTML(row.Product)}</span><strong class="${row.Gap<0?'negative':'positive'}">${signed(row.Gap)}</strong></div><div class="rank-track"><span style="width:${Math.max(2,Math.abs(row.Gap)/max*100)}%"></span></div>`;
    button.addEventListener('click',()=>{state.product=state.product===row.Product?'':row.Product;$('product-select').value=state.product;render();});
    $('product-ranking').append(button);
  }
  $('analysis-product-rows').replaceChildren(...grouped.map(row=>{
    const tr=document.createElement('tr');
    tr.className=row.Product===state.product?'selected-product-row':'';
    const productCell=document.createElement('td');
    const button=document.createElement('button');button.className='product-detail-button';button.textContent=row.Product;
    button.setAttribute('aria-label',`${row.Product}, Gap ${signed(row.Gap)}. Phân rã theo State`);
    button.setAttribute('aria-pressed',String(row.Product===state.product));
    button.addEventListener('click',()=>{state.product=state.product===row.Product?'':row.Product;$('product-select').value=state.product;render();});
    productCell.append(button);tr.append(productCell);
    for(const field of ['Sales','BudgetSales','Gap']){
      const cell=document.createElement('td');cell.textContent=field==='Gap'?signed(row[field]):fmt(row[field]);
      if(field==='Gap')cell.className=row.Gap<0?'negative':'positive';
      tr.append(cell);
    }
    return tr;
  }));
}

function updateMarketCards(){
  $('drill-title').textContent=state.product?`${state.product} ở các thị trường`:'Thị trường nào cần chú ý?';
  $('drill-caption').textContent=`${monthName(state.month)} · ${state.product||'Tất cả sản phẩm'}. Chọn Market để soi sâu hơn; các thẻ cùng kỳ và cùng phạm vi sản phẩm.`;
  $('market-cards').replaceChildren();
  for(const market of payload.meta.markets){
    const total=sumRows(filteredRows({market}));
    const ratio=total&&total.BudgetSales!==0?total.Sales/total.BudgetSales:null;
    const button=document.createElement('button');button.className=`market-card ${state.market===market?'selected':''}`;
    button.setAttribute('aria-pressed',String(state.market===market));
    button.innerHTML=`<div><span>${escapeHTML(market)}</span><span class="mc-gap ${total?.Gap<0?'negative':'positive'}">${total?signed(total.Gap):'—'}</span></div><strong>${fmt(total?.Sales??null)}</strong><small>${total?'Sales thực tế':'Không có bản ghi ở tổ hợp này'}</small><div class="mc-budget"><span>Budget ${fmt(total?.BudgetSales??null)}</span><span>${ratio===null?'—':percent.format(ratio)}</span></div>`;
    button.addEventListener('click',()=>{state.market=state.market===market?'':market;$('market-select').value=state.market;render();});
    $('market-cards').append(button);
  }
}

async function updateStateDrill(){
  const myId=++requestId;
  $('state-section').hidden=true;
  $('state-empty').hidden=Boolean(state.market&&state.product);
  if(!state.market||!state.product)return;
  const selectedRows=filteredRows();
  if(!selectedRows.length)return;
  const productNames=[...new Set(selectedRows.map(row=>row.ProductName))];
  const snapshot={...state};
  $('state-section').hidden=false;$('state-title').textContent=`${state.product} → State`;$('state-caption').textContent=`${state.market} · ${monthName(state.month)} · đang đọc chi tiết từ kho…`;$('state-list').replaceChildren();
  try{
    const replies=await Promise.all(productNames.map(async product=>{
      const params=new URLSearchParams({month:snapshot.month,market:snapshot.market,product});
      const reply=await fetch(`/api/drill?${params}`);const result=await reply.json();if(!reply.ok)throw new Error(result.error||'Không đọc được chi tiết State.');return result.rows;
    }));
    if(myId!==requestId)return;
    const rows=groupRows(replies.flat(),row=>row.State).sort((a,b)=>a.Gap-b.Gap||a.State.localeCompare(b.State));
    const total=sumRows(rows),expected=sumRows(selectedRows);
    const match=Boolean(total&&expected&&moneyFields.every(field=>Math.abs(total[field]-expected[field])<.01));
    $('state-caption').textContent=`${snapshot.market} · ${monthName(snapshot.month)} · ${rows.length} State. ${match?'Tổng State khớp ô đang xem.':'Cần kiểm tra lại đối soát State.'} Đây là phân rã số liệu, không khẳng định nguyên nhân.`;
    if(!match)throw new Error('Tổng drill-down State không khớp mart sản phẩm; không dùng kết quả này để kết luận.');
    $('state-list').replaceChildren(...rows.map(row=>{
      const element=document.createElement('div');element.className='state-item';
      element.innerHTML=`<div>${escapeHTML(row.State)}<br><small>Sales ${fmt(row.Sales)} / Budget ${fmt(row.BudgetSales)}</small></div><strong class="${row.Gap<0?'negative':'positive'}">${signed(row.Gap)}</strong>`;return element;
    }));
  }catch(error){
    if(myId!==requestId)return;$('state-caption').textContent=error.message;$('state-list').replaceChildren();
  }
}

function render(){
  if(!payload||!scene)return;
  $('error-banner').hidden=true;
  rebuildCube();syncAnalysisFilters();updateKpis();updateRanking();updateMarketCards();updateStateDrill();
}

function selectCubeCell(row){
  state.month=row.MonthStart;state.market=row.Market;state.product=row.Product;
  $('market-select').value=state.market;$('product-select').value=state.product;
  render();toast(`${row.Market} · ${row.Product} · ${monthName(row.MonthStart)}`);
}

function changeMonth(delta){
  const index=months.indexOf(state.month);const next=months[Math.max(0,Math.min(months.length-1,index+delta))];
  if(next!==state.month){state.month=next;render();}
}

function setCase(name){
  state.level='product';state.measure='Gap';state.mode='slice';state.pivot=false;
  if(name==='south'){state.year='2013';state.month='2013-08-01';state.market='South';state.product='';}
  else{state.year='2012';state.month='2012-01-01';state.market='Central';state.product='';}
  $('year-select').value=state.year;$('market-select').value=state.market;$('measure-select').value=state.measure;syncProductOptions();
  render();showView('analysis');toast(name==='south'?'South hụt 9 ở tổng Market. Chọn Colombian để thấy phần hụt 268.':'Central vượt 376. Chọn một sản phẩm để xem phân rã theo State.');
}

function showView(view){
  const selected=view===true?'lineage':view===false?'explore':view;
  state.view=selected;
  $('explorer').hidden=selected!=='explore';$('view-intro').hidden=selected!=='explore';
  $('drill-section').hidden=selected!=='analysis';$('lineage-section').hidden=selected!=='lineage';
  for(const name of ['explore','analysis','lineage']){
    const tab=$(`${name}-tab`),active=name===selected;
    tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));tab.setAttribute('tabindex',active?'0':'-1');
  }
  if(selected==='explore')requestAnimationFrame(()=>scene?.resize());
}

function exportCsv(){
  const rows=filteredRows();
  const fields=['MonthStart','Market','ProductName','Sales','BudgetSales','Profit','Gap'];
  const quote=value=>{let text=String(value??'');if(typeof value==='string'&&/^[=+@-]/.test(text))text=`'${text}`;return `"${text.replace(/"/g,'""')}"`;};
  const content='\ufeff'+[fields,...rows.map(row=>fields.map(field=>row[field]))].map(row=>row.map(quote).join(',')).join('\r\n');
  const blob=new Blob([content],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=`coffee_cube_${state.month.slice(0,7)}_${state.market||'all'}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast(`Đã xuất ${rows.length} ô mart đúng phạm vi tháng, Market và sản phẩm đang chọn.`);
}

function wireControls(){
  $('year-select').addEventListener('change',e=>{state.year=e.target.value;render();});
  $('market-select').addEventListener('change',e=>{state.market=e.target.value;render();});
  $('product-select').addEventListener('change',e=>{state.product=e.target.value;render();});
  $('measure-select').addEventListener('change',e=>{state.measure=e.target.value;render();});
  $('month-slider').addEventListener('input',e=>{state.month=months[Number(e.target.value)];render();});
  $('prev-month').addEventListener('click',()=>changeMonth(-1));$('next-month').addEventListener('click',()=>changeMonth(1));
  for(const button of $('level-control').querySelectorAll('button'))button.addEventListener('click',()=>{state.level=button.dataset.level;state.product='';syncProductOptions();render();});
  for(const button of $('view-control').querySelectorAll('button'))button.addEventListener('click',()=>{state.mode=button.dataset.mode;render();});
  $('pivot-button').addEventListener('click',()=>{state.pivot=!state.pivot;render();toast('Đã đổi trục tháng và sản phẩm; các số đo không thay đổi.');});
  $('reset-camera').addEventListener('click',()=>scene.reset());
  $('case-south').addEventListener('click',()=>setCase('south'));$('case-central').addEventListener('click',()=>setCase('central'));
  $('clear-product').addEventListener('click',()=>{state.product='';$('product-select').value='';render();});
  $('analysis-month-select').addEventListener('change',event=>{
    state.month=event.target.value;
    if(state.year!=='all'&&!state.month.startsWith(state.year)){state.year=state.month.slice(0,4);$('year-select').value=state.year;}
    render();
  });
  $('analysis-market-select').addEventListener('change',event=>{state.market=event.target.value;$('market-select').value=state.market;render();});
  $('analysis-product-select').addEventListener('change',event=>{state.product=event.target.value;$('product-select').value=state.product;render();});
  $('analysis-level-select').addEventListener('change',event=>{state.level=event.target.value;state.product='';syncProductOptions();render();});
  const tabNames=['explore','analysis','lineage'];
  tabNames.forEach((view,index)=>{
    const tab=$(`${view}-tab`);
    tab.addEventListener('click',()=>showView(view));
    tab.addEventListener('keydown',event=>{
      if(event.altKey||event.ctrlKey||event.metaKey)return;
      let next;
      if(event.key==='ArrowRight')next=(index+1)%tabNames.length;
      else if(event.key==='ArrowLeft')next=(index+tabNames.length-1)%tabNames.length;
      else if(event.key==='Home')next=0;
      else if(event.key==='End')next=tabNames.length-1;
      else return;
      event.preventDefault();$(`${tabNames[next]}-tab`).focus();showView(tabNames[next]);
    });
  });
  $('return-explorer').addEventListener('click',()=>showView('explore'));
  $('analysis-back').addEventListener('click',()=>showView('explore'));
  $('export-button').addEventListener('click',exportCsv);
  $('source-info').addEventListener('click',()=>$('source-dialog').showModal());$('close-dialog').addEventListener('click',()=>$('source-dialog').close());
  $('source-dialog').addEventListener('click',event=>{if(event.target===$('source-dialog')){const rect=$('source-dialog').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)$('source-dialog').close();}});
}

async function boot(){
  try{
    const response=await fetch('/api/data');const data=await response.json();if(!response.ok)throw new Error(data.error||'Chưa đọc được kho dữ liệu.');
    payload=data;
    if(!payload.meta.months.length||!payload.productPeriod.length)throw new Error('Mart chưa có ô dữ liệu.');
    const mapping=payload.meta.productTypes;
    if(!mapping||payload.meta.products.some(product=>!mapping[product]))throw new Error('Thiếu ánh xạ nhóm sản phẩm từ DimProduct.');
    if(!payload.meta.months.includes(state.month))state.month=payload.meta.months.at(-1);
    if(!payload.meta.months.some(month=>month.startsWith(state.year)))state.year=state.month.slice(0,4);
    $('month-count').textContent=payload.meta.months.length;$('market-count').textContent=payload.meta.markets.length;$('product-count').textContent=payload.meta.products.length;
    $('source-label').textContent=payload.meta.backend==='sqlserver'?'SQL Server · mart trực tiếp':'SQLite · kho tham chiếu';
    $('source-details').innerHTML=`<p><strong>${escapeHTML(payload.meta.sourceLabel)}</strong></p><p>Database: <code>${escapeHTML(payload.meta.database||'SQLite')}</code></p><p><code>vw_MarketPeriod</code> · ${fmt(payload.marketPeriod.length)} ô<br><code>vw_MarketProductPeriod</code> · ${fmt(payload.productPeriod.length)} ô</p><p>Sales toàn nguồn ${fmt(payload.meta.totals?.Sales??sumRows(payload.marketPeriod).Sales)} · Budget ${fmt(payload.meta.totals?.BudgetSales??sumRows(payload.marketPeriod).BudgetSales)} · Profit ${fmt(payload.meta.totals?.Profit??sumRows(payload.marketPeriod).Profit)}</p>`;
    $('footer-source').textContent=payload.meta.backend==='sqlserver'?'SQL Server · SELECT chỉ đọc':'SQLite · kết nối chỉ đọc';
    prepareOptions();
    if(window.matchMedia){
      const wideFilters=window.matchMedia('(min-width: 901px)');
      $('filter-details').open=wideFilters.matches;
      wideFilters.addEventListener('change',event=>{$('filter-details').open=event.matches;});
    }else if(window.innerWidth<900)$('filter-details').open=false;
    scene=new CubeScene($('viewport'),selectCubeCell);
    wireControls();render();$('loading-state').hidden=true;
    // Compact, read-only diagnostics for repeatable technical QA of the scene.
    window.coffeeAtlas={getState:()=>({...state}),getSummary:()=>({source:payload.meta.backend,visibleMonths:months.length,cubeCells:cubeRows.length,scopeRows:filteredRows().length,scopeTotals:sumRows(filteredRows())})};
  }catch(error){
    $('loading-state').hidden=true;showError(`Không mở được khối dữ liệu: ${error.message}`);
    $('source-label').textContent='Chưa kết nối';
  }
}
boot();
