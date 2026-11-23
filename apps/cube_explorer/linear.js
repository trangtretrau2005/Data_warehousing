const state={payload:null,market:null,scenarioPct:0};
const $=selector=>document.querySelector(selector);
const number=new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2});
const fmt=value=>Number.isFinite(value)?number.format(value):'—';
const month=value=>new Intl.DateTimeFormat('vi-VN',{month:'2-digit',year:'numeric'}).format(new Date(`${value}T00:00:00`));

function svg(tag,attributes={},text=''){
  const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
  Object.entries(attributes).forEach(([key,value])=>node.setAttribute(key,value));
  if(text)node.textContent=text;
  return node;
}

function scale(domainMin,domainMax,rangeMin,rangeMax){
  const span=domainMax-domainMin||1;
  return value=>rangeMin+(value-domainMin)/span*(rangeMax-rangeMin);
}

function drawChart(model,scenarioMarketing,scenarioSales){
  const chart=$('#scatter'),width=Math.max(chart.clientWidth||760,320),height=chart.clientHeight||430;
  chart.setAttribute('viewBox',`0 0 ${width} ${height}`);chart.replaceChildren();
  const margin={left:66,right:24,top:24,bottom:54};
  const allX=[...model.points.map(point=>point.marketing),...model.line.map(point=>point.marketing),scenarioMarketing];
  const allY=[...model.points.map(point=>point.sales),...model.line.map(point=>point.prediction),scenarioSales];
  const xPad=(Math.max(...allX)-Math.min(...allX)||1)*.06,yPad=(Math.max(...allY)-Math.min(...allY)||1)*.08;
  const x=scale(Math.min(...allX)-xPad,Math.max(...allX)+xPad,margin.left,width-margin.right);
  const y=scale(Math.min(...allY)-yPad,Math.max(...allY)+yPad,height-margin.bottom,margin.top);
  for(let i=0;i<=5;i++){
    const gx=margin.left+(width-margin.left-margin.right)*i/5;
    const gy=margin.top+(height-margin.top-margin.bottom)*i/5;
    chart.append(svg('line',{x1:gx,y1:margin.top,x2:gx,y2:height-margin.bottom,class:'grid-line'}));
    chart.append(svg('line',{x1:margin.left,y1:gy,x2:width-margin.right,y2:gy,class:'grid-line'}));
    const xv=(Math.min(...allX)-xPad)+(Math.max(...allX)-Math.min(...allX)+2*xPad)*i/5;
    const yv=(Math.max(...allY)+yPad)-(Math.max(...allY)-Math.min(...allY)+2*yPad)*i/5;
    chart.append(svg('text',{x:gx,y:height-margin.bottom+20,'text-anchor':'middle',class:'tick-label'},fmt(xv)));
    chart.append(svg('text',{x:margin.left-10,y:gy+4,'text-anchor':'end',class:'tick-label'},fmt(yv)));
  }
  chart.append(svg('line',{x1:margin.left,y1:height-margin.bottom,x2:width-margin.right,y2:height-margin.bottom,class:'axis-line'}));
  chart.append(svg('line',{x1:margin.left,y1:margin.top,x2:margin.left,y2:height-margin.bottom,class:'axis-line'}));
  chart.append(svg('text',{x:(margin.left+width-margin.right)/2,y:height-12,'text-anchor':'middle',class:'axis-title'},'Marketing · tổng theo Market–tháng'));
  const yTitle=svg('text',{x:16,y:(margin.top+height-margin.bottom)/2,transform:`rotate(-90 16 ${(margin.top+height-margin.bottom)/2})`,'text-anchor':'middle',class:'axis-title'},'Sales · tổng theo Market–tháng');chart.append(yTitle);
  chart.append(svg('line',{x1:x(model.line[0].marketing),y1:y(model.line[0].prediction),x2:x(model.line[1].marketing),y2:y(model.line[1].prediction),class:'regression-line'}));
  model.points.forEach(point=>{
    const circle=svg('circle',{cx:x(point.marketing),cy:y(point.sales),r:point.split==='train'?5.5:6.5,class:point.split==='train'?'point-train':'point-test'});
    circle.append(svg('title',{},`${month(point.month)} · Marketing ${fmt(point.marketing)} · Sales ${fmt(point.sales)} · ${point.split}`));chart.append(circle);
  });
  const diamond=svg('rect',{x:x(scenarioMarketing)-7,y:y(scenarioSales)-7,width:14,height:14,transform:`rotate(45 ${x(scenarioMarketing)} ${y(scenarioSales)})`,class:'scenario-point'});
  diamond.append(svg('title',{},`Kịch bản · Marketing ${fmt(scenarioMarketing)} · Sales ${fmt(scenarioSales)}`));chart.append(diamond);
}

function quality(model){
  if(model.testR2<0)return ['Chưa đủ tốt để dự báo','R² test âm'];
  if(model.testR2<.3)return ['Khả năng giải thích thấp',`R² test ${fmt(model.testR2)}`];
  return ['Có tín hiệu trên test',`R² test ${fmt(model.testR2)}`];
}

function render(){
  const model=state.payload.markets.find(item=>item.market===state.market);
  const pct=state.scenarioPct,scenarioMarketing=model.referenceMarketing*(1+pct/100);
  const scenarioSales=model.intercept+model.coefficient*scenarioMarketing;
  const delta=scenarioSales-model.referencePrediction;
  $('#market-title').textContent=`${model.market} · ${model.trainN} train / ${model.testN} test`;
  $('#equation').textContent=`Sales = ${fmt(model.intercept)} + ${fmt(model.coefficient)} × Marketing`;
  const [badge,help]=quality(model);$('#quality-badge').textContent=badge;
  $('#metric-corr').textContent=fmt(model.correlationAll);$('#metric-mae').textContent=fmt(model.testMAE);$('#metric-rmse').textContent=fmt(model.testRMSE);$('#metric-r2').textContent=fmt(model.testR2);$('#r2-help').textContent=help;
  $('#scenario-pct').textContent=`${pct>0?'+':''}${pct}%`;$('#scenario-marketing').textContent=fmt(scenarioMarketing);$('#scenario-sales').textContent=fmt(scenarioSales);
  $('#scenario-delta').textContent=`${delta>=0?'+':''}${fmt(delta)} so với điểm tham chiếu của đường hồi quy (${month(model.referenceMonth)}).`;
  $('#coefficient-reading').textContent=`Trong tập train, Marketing tăng 1 đơn vị đi cùng Sales tăng trung bình ${fmt(model.coefficient)} đơn vị theo đường thẳng. Đây là liên hệ, không phải tác động nhân quả.`;
  $('#test-reading').textContent=`MAE Linear ${fmt(model.testMAE)}, so với baseline trung bình train ${fmt(model.baselineMAE)}. R² test ${fmt(model.testR2)} cho thấy mô hình chưa giải thích tốt biến động sáu tháng cuối.`;
  $('#point-count').textContent=`${model.n} tháng · test từ ${month(state.payload.meta.testStart)}`;
  drawChart(model,scenarioMarketing,scenarioSales);
}

function renderTable(){
  $('#market-table').innerHTML=state.payload.markets.map(model=>`<tr><td>${model.market}</td><td>${fmt(model.correlationAll)}</td><td>${fmt(model.coefficient)}</td><td>${fmt(model.testMAE)}</td><td>${fmt(model.baselineMAE)}</td><td class="${model.testR2<0?'bad':''}">${fmt(model.testR2)}</td><td>${model.testR2<0?'Không dùng thay forecast':'Cần kiểm thêm'}</td></tr>`).join('');
}

async function init(){
  try{
    const response=await fetch('/api/linear'),payload=await response.json();
    if(!response.ok)throw new Error(payload.error||'Không đọc được kết quả Linear Regression.');
    state.payload=payload;state.market=payload.markets[0].market;
    $('#source-label').textContent=payload.meta.sourceLabel;
    $('#market-select').innerHTML=payload.markets.map(model=>`<option value="${model.market}">${model.market}</option>`).join('');
    $('#train-range').textContent=`${month(payload.meta.trainStart)} → ${month(payload.meta.trainEnd)}`;
    $('#test-range').textContent=`${month(payload.meta.testStart)} → ${month(payload.meta.testEnd)}`;
    $('#scenario-slider').min=payload.meta.scenarioMinPct;$('#scenario-slider').max=payload.meta.scenarioMaxPct;
    $('#workspace').hidden=false;$('#comparison').hidden=false;renderTable();render();
  }catch(error){$('#error').textContent=error.message;$('#error').hidden=false;}
}

$('#market-select').addEventListener('change',event=>{state.market=event.target.value;state.scenarioPct=0;$('#scenario-slider').value=0;render();});
$('#scenario-slider').addEventListener('input',event=>{state.scenarioPct=Number(event.target.value);render();});
window.addEventListener('resize',()=>{if(state.payload)render();});
init();
