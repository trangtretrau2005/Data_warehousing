// Component logic tests in Node's VM, without browser/computer automation.
// Data below is synthetic unit-test input, never published as research results.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup(actual = 120, blocked = false, researchBacked = false) {
  const html = fs.readFileSync(path.join(__dirname, '../apps/forecast_demo/presenter.html'), 'utf8');
  const source = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {textContent:'',disabled:false,style:{},className:'',
      classList:{toggle(){}},setAttribute(){},dataset:{}});
    return elements.get(id);
  }
  const steps = [0,1,2].map(i => ({...element('step'+i),dataset:{stage:String(i)}}));
  const listeners = {};
  class FakeAudio {
    constructor(){this.src='';this.currentTime=0;this.events={};}
    play(){return blocked ? Promise.reject(new Error('autoplay blocked')) : Promise.resolve();}
    pause(){}
    removeAttribute(){this.src='';}
    load(){}
    addEventListener(name, handler){this.events[name]=handler;}
  }
  const forecastCase = {
    market:'West',forecast_month:'2013-10-01',issue_month:'2013-09-01',method:'ridge',
    prediction:110,last_actual:100,actual,
    validation_market:{MAE:12,N:6},
    report:{known_through:'2013-09-01',latest_sales:100,latest_budget:80,latest_profit:25,
      budget_ratio:1.25,profit_ratio:.25,last_change:10,
      recent:[{month:'2013-08-01',sales:90,budget:80},{month:'2013-09-01',sales:100,budget:80}],
      products:[{name:'Coffee A',sales:60,share:.6},{name:'Coffee B',sales:40,share:.4}]},
    history:[{month:'2013-08-01',sales:90},{month:'2013-09-01',sales:100}],
    explanation:{base_value:100,reconstruction_error:0,features:[
      {month:'2013-09-01',contribution:20},{month:'2013-08-01',contribution:-15},
      {month:'2013-07-01',contribution:5}]},
    chapters:[{text:'forecast text'},{text:'explanation text'},{text:'quality text'}],
    market_comparison:[{method:'naive_last',MAE:15},{method:'moving_average_3',MAE:10},{method:'ridge',MAE:12}]
  };
  const payload = {case:forecastCase,audio:['data:audio/wav;base64,AAA','data:audio/wav;base64,BBB','data:audio/wav;base64,CCC'],
    methods:{naive_last:'Tháng trước',moving_average_3:'Trung bình 3 tháng',ridge:'Ridge · 3 độ trễ'},
    selected_method:'moving_average_3',voice:{status:'ready'}};
  if(researchBacked){
    forecastCase.method='moving_average_3';
    forecastCase.story={is_selected:true,formula:'(90 + 110 + 130) / 3 = 110',
      inputs:[{month:'2013-07-01',sales:90},{month:'2013-08-01',sales:110},{month:'2013-09-01',sales:130}],
      validation_history:[{month:'2013-04-01',actual:100,prediction:105},{month:'2013-05-01',actual:110,prediction:106}]};
    payload.research={candidate_count:7,validation_mae:10,gain_vs_previous_pct:0,reconciled_monthly_cells:96,
      leaderboard:[{Label:'MA3',MAE:10,Selected:true},{Label:'Naive',MAE:15,Selected:false}]};
  }
  const plots=[];
  const context=vm.createContext({Intl,Audio:FakeAudio,document:{getElementById:element,querySelectorAll:()=>steps},
    Plotly:{react:(id,traces,layout)=>plots.push({id,traces,layout})},
    window:{addEventListener:(name,handler)=>listeners[name]=handler}});
  vm.runInContext(source.replace('__DATA_JSON__',JSON.stringify(payload)),context);
  return {context,element,plots,steps,get:code=>vm.runInContext(code,context)};
}

test('forecast is visible before actual is revealed',()=>{
  const s=setup();
  assert.equal(s.plots.at(-1).traces[1].y[1],110);
  assert.equal(s.element('actual').textContent,'');
  assert.equal(s.element('reveal').style.display,'none');
});

test('waterfall keeps each signed contribution and total',()=>{
  const s=setup();s.get('setStage(1)');
  assert.equal(s.plots.at(-1).traces[0].type,'waterfall');
  assert.deepEqual(Array.from(s.plots.at(-1).traces[0].y),[100,20,-15,5,0]);
  assert.match(s.element('insight').textContent,/không phải bằng chứng/);
});

test('only an explicit reveal shows held-out actual',()=>{
  const s=setup();s.get('setStage(2)');
  assert.equal(s.element('actual').textContent,'');
  s.element('reveal-button').onclick();
  assert.match(s.element('actual').textContent,/120/);
  assert.match(s.element('actual').textContent,/10/);
});

test('future target without actual disables the reveal action',()=>{
  const s=setup(null);s.get('setStage(2)');
  assert.equal(s.element('reveal-button').disabled,true);
  s.element('reveal-button').onclick();
  assert.equal(s.element('actual').textContent,'');
});

test('play, pause and audio-ended events advance three chapters',async()=>{
  const s=setup();s.element('play').onclick();await Promise.resolve();
  assert.equal(s.get('playing'),true);
  s.element('play').onclick();assert.equal(s.get('playing'),false);
  s.element('play').onclick();await Promise.resolve();
  s.get("player.events.ended()");await Promise.resolve();
  assert.equal(s.get('stage'),1);
  s.get("player.events.ended()");await Promise.resolve();
  assert.equal(s.get('stage'),2);
  s.get("player.events.ended()");
  assert.equal(s.get('finished'),true);
  assert.equal(s.get('playing'),false);
});

test('blocked audio retains captions and gives a retry message',async()=>{
  const s=setup(120,true);s.element('play').onclick();
  await Promise.resolve();await Promise.resolve();
  assert.equal(s.get('playing'),false);
  assert.match(s.element('play-state').textContent,/chưa phát được/);
  assert.equal(s.element('caption').textContent,'forecast text');
});

test('management context and cautious action use only origin information',()=>{
  const s=setup();
  assert.match(s.element('known-budget').textContent,/125/);
  assert.match(s.element('known-profit').textContent,/25/);
  assert.equal(s.element('priority-title').textContent,'Coffee A');
  assert.match(s.element('signal-title').textContent,/nhỏ/);
  assert.equal(s.plots.find(p=>p.id==='budget-chart').traces[0].y[1],100);
  assert.equal(s.element('actual').textContent,'');
});

test('listener can slow down speech without changing chapter or data',()=>{
  const s=setup();s.element('speed').onchange({target:{value:'0.9'}});
  assert.equal(s.get('player.playbackRate'),.9);
  assert.equal(s.get('stage'),0);
  assert.equal(s.element('actual').textContent,'');
});

test('research-backed MA3 shows three inputs and the exact mean formula',()=>{
  const s=setup(120,false,true);s.get('setStage(1)');
  assert.equal(s.plots.at(-1).traces[0].type,'bar');
  assert.deepEqual(Array.from(s.plots.at(-1).traces[0].y),[90,110,130]);
  assert.equal(s.element('formula').hidden,false);
  assert.match(s.element('formula').textContent,/90 \+ 110 \+ 130/);
  assert.equal(s.plots.at(-1).layout.shapes[0].y0,110);
  assert.equal(s.element('actual').textContent,'');
});

test('research-backed quality uses validation history, never target actual',()=>{
  const s=setup(999999,false,true);s.get('setStage(2)');
  assert.deepEqual(Array.from(s.plots.at(-1).traces[0].y),[100,110]);
  assert.deepEqual(Array.from(s.plots.at(-1).traces[1].y),[105,106]);
  assert.equal(s.element('actual').textContent,'');
  assert.equal(s.element('research-section').hidden,false);
  assert.match(s.element('research-summary').textContent,/7 cấu hình/);
});
