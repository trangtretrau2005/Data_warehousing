import * as THREE from './vendor/three.module.min.js';

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const color = value => new THREE.Color(value);
const fmt = value => new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 0}).format(value);
const monthName = month => `${month.slice(5,7)}/${month.slice(0,4)}`;
const shortName = name => ({'Decaf Irish Cream':'Decaf Irish', 'Regular Espresso':'Reg. Espresso', 'Decaf Espresso':'Decaf Esp.', 'Caffe Mocha':'C. Mocha', 'Caffe Latte':'C. Latte', 'Herbal Tea':'Herbal Tea'})[name] || name;

export class CubeScene {
  constructor(viewport, onSelect) {
    this.viewport = viewport;
    this.canvas = viewport.querySelector('canvas');
    this.labelRoot = viewport.querySelector('#axis-labels');
    this.tooltip = viewport.querySelector('#cube-tooltip');
    this.onSelect = onSelect;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(36, 1, .1, 100);
    this.renderer = new THREE.WebGLRenderer({canvas: this.canvas, antialias: true, alpha: true, powerPreference:'low-power'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.setClearColor(0x17223d, 0);
    this.scene.add(new THREE.AmbientLight(0xe7edff, 2.0));
    const sun = new THREE.DirectionalLight(0xffffff, 2.6);
    sun.position.set(1, 8, 5);
    this.scene.add(sun);
    const bounce = new THREE.DirectionalLight(0xaec7ff, 1.1);
    bounce.position.set(-5, 1, -4);
    this.scene.add(bounce);
    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1,1,1),
      new THREE.MeshStandardMaterial({color:0xffffff, roughness:.56, metalness:.1}),
      2000,
    );
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.count=0;
    this.mesh.frustumCulled=false;
    this.group.add(this.mesh);
    const outlineMaterial = new THREE.LineBasicMaterial({color:0xf5dfad, transparent:true, opacity:.95});
    this.outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1)), outlineMaterial);
    this.outline.visible=false;
    this.group.add(this.outline);
    this.sliceFrame=new THREE.LineSegments(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:0xd8c496,transparent:true,opacity:.55}));
    this.group.add(this.sliceFrame);
    this.slicePlane=new THREE.Mesh(new THREE.PlaneGeometry(5.25,4.1),new THREE.MeshBasicMaterial({color:0xe0cea0,transparent:true,opacity:.035,depthWrite:false,side:THREE.DoubleSide}));
    this.slicePlane.rotation.y=Math.PI/2;
    this.group.add(this.slicePlane);
    const grid = new THREE.GridHelper(16, 24, 0x647aaf, 0x3a527c);
    grid.position.y=-2.9;
    grid.material.transparent=true;
    grid.material.opacity=.24;
    this.scene.add(grid);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(17,12),new THREE.MeshBasicMaterial({color:0x3e4d83,transparent:true,opacity:.17,side:THREE.DoubleSide}));
    floor.rotation.x=-Math.PI/2;
    floor.position.y=-2.92;
    this.scene.add(floor);
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.spherical={theta:.74,phi:1.12,radius:14.2};
    this.desired={...this.spherical};
    this.cameraTarget = new THREE.Vector3(0,-.1,0);
    this.rows=[];this.axes=[];this.selectedIndex=-1;this.hoverIndex=-1;
    this.matrix = new THREE.Object3D();
    this.down=null;this.dragged=false;
    this.canvas.addEventListener('pointerdown',e=>{this.down={x:e.clientX,y:e.clientY,theta:this.desired.theta,phi:this.desired.phi};this.dragged=false;this.canvas.setPointerCapture(e.pointerId);this.tooltip.hidden=true;});
    this.canvas.addEventListener('pointermove',e=>this.pointerMove(e));
    this.canvas.addEventListener('pointerup',e=>this.pointerUp(e));
    this.canvas.addEventListener('pointercancel',()=>{this.down=null;this.canvas.classList.remove('dragging');});
    this.canvas.addEventListener('pointerleave',()=>{if(!this.down){this.tooltip.hidden=true;this.hoverIndex=-1;}});
    this.canvas.addEventListener('wheel',e=>{e.preventDefault();this.desired.radius=Math.min(28,Math.max(10,this.desired.radius+e.deltaY*.012));},{passive:false});
    this.canvas.addEventListener('keydown',e=>{
      if(e.key==='ArrowLeft')this.desired.theta-=.12;
      else if(e.key==='ArrowRight')this.desired.theta+=.12;
      else if(e.key==='ArrowUp')this.desired.phi=Math.max(.35,this.desired.phi-.08);
      else if(e.key==='ArrowDown')this.desired.phi=Math.min(1.6,this.desired.phi+.08);
      else if(e.key==='+'||e.key==='=')this.desired.radius=Math.max(10,this.desired.radius-1);
      else if(e.key==='-')this.desired.radius=Math.min(28,this.desired.radius+1);
      else return;
      e.preventDefault();
    });
    this.resizeObserver=new ResizeObserver(()=>this.resize());
    this.resizeObserver.observe(viewport);
    this.resize();
    this.lastFrame=performance.now();
    this.animate=this.animate.bind(this);requestAnimationFrame(this.animate);
    this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();document.dispatchEvent(new CustomEvent('cube-error',{detail:'Trình duyệt đã tạm ngắt đồ họa 3D. Tải lại trang để mở lại khối; các số liệu mart không thay đổi.'}));});
  }

  resize(){
    const {width,height}=this.viewport.getBoundingClientRect();
    if(!width||!height)return;
    this.renderer.setSize(width,height,false);this.camera.aspect=width/height;this.camera.updateProjectionMatrix();
  }

  reset(){this.desired={theta:.74,phi:1.12,radius:14.2};}

  setData(rows, state, months, markets, products){
    this.hoverIndex=-1;
    const wasEmpty=!this.rows.length;
    const previous=new Map(this.rows.map(r=>[r.key,r]));
    const xSpace=state.rollup?1.45:8.1/Math.max(months.length,1);
    const ySpace=1.03;
    const zSpace=state.rollup?1.45:4.7/Math.max(products.length,1);
    const maxAbs=Math.max(...rows.map(r=>Math.abs(r[state.measure])),1);
    const min=Math.min(...rows.map(r=>r[state.measure]),0);
    const max=Math.max(...rows.map(r=>r[state.measure]),1);
    const focusProducts=Array.isArray(state.focusProducts)?state.focusProducts:[];
    this.state=state;this.months=months;this.products=products;this.markets=markets;
    this.rows=rows.map(r=>{
      const index=months.indexOf(r.MonthStart);
      const monthActive=r.MonthStart===state.month;
      const marketActive=!state.market||r.Market===state.market;
      const productActive=state.product?r.Product===state.product:(!focusProducts.length||focusProducts.includes(r.Product));
      const active=monthActive&&marketActive&&productActive;
      const focus=marketActive&&productActive;
      const isHidden=state.mode==='slice'&&(!monthActive||!focus);
      let x=(index-(months.length-1)/2)*xSpace;
      let y=(markets.indexOf(r.Market)-(markets.length-1)/2)*ySpace;
      let z=(products.indexOf(r.Product)-(products.length-1)/2)*zSpace;
      if(state.mode==='slice')x=0;
      if(state.mode==='explode')x*=1.23;
      if(state.pivot)[x,z]=[z,x];
      const target=new THREE.Vector3(x,y,z);
      let baseColor;
      if(state.measure==='Gap'||min<0){
        const magnitude=Math.pow(Math.min(Math.abs(r[state.measure])/maxAbs,1),.48);
        baseColor=color('#bcc8e8').lerp(color(r[state.measure]<0?'#e48485':'#64cfbc'),magnitude);
      }else{
        const fraction=(r[state.measure]-min)/(max-min||1);
        baseColor=color('#c4cef6').lerp(color('#7a9be6'),Math.pow(fraction,.65));
      }
      if(!focus)baseColor.lerp(color('#253759'),.84);
      else if(!monthActive&&state.mode!=='all')baseColor.lerp(color('#28395c'),.72);
      const key=`${r.MonthStart}|${r.Market}|${r.Product}`;
      const prev=previous.get(key);
      const scale=new THREE.Vector3(xSpace*.83,.8,zSpace*.79);
      if(state.pivot)[scale.x,scale.z]=[scale.z,scale.x];
      if(isHidden)scale.set(0,0,0);
      if(!focus&&state.mode!=='slice')scale.multiplyScalar(.48);
      if(monthActive&&focus)scale.multiplyScalar(1.04);
      return {...r,key,target,position:prev?prev.position.clone():target.clone(),scale,targetColor:baseColor,currentColor:prev?prev.currentColor.clone():baseColor.clone(),currentScale:prev?prev.currentScale.clone():scale.clone(),active,hidden:isHidden};
    });
    this.mesh.count=this.rows.length;
    let sliceX=(months.indexOf(state.month)-(months.length-1)/2)*xSpace;
    if(state.mode==='slice')sliceX=0;
    if(state.mode==='explode')sliceX*=1.23;
    const corners=[new THREE.Vector3(sliceX,-2.05,-2.62),new THREE.Vector3(sliceX,2.05,-2.62),new THREE.Vector3(sliceX,2.05,2.62),new THREE.Vector3(sliceX,-2.05,2.62)];
    if(state.pivot)corners.forEach(point=>{[point.x,point.z]=[point.z,point.x];});
    const framePoints=[];for(let i=0;i<4;i++)framePoints.push(corners[i],corners[(i+1)%4]);
    this.sliceFrame.geometry.dispose();this.sliceFrame.geometry=new THREE.BufferGeometry().setFromPoints(framePoints);
    this.slicePlane.rotation.y=state.pivot?0:Math.PI/2;
    this.slicePlane.position.set(state.pivot?0:sliceX,0,state.pivot?sliceX:0);
    this.selectedIndex=this.rows.findIndex(r=>r.MonthStart===state.month&&r.Market===state.market&&r.Product===state.product);
    this.axes=[];this.labelRoot.replaceChildren();
    const addLabel=(text,position,className='')=>{
      const node=document.createElement('span');node.className=`axis-label ${className}`;node.textContent=text;this.labelRoot.append(node);this.axes.push({node,position,fixed:className.includes('title-label')});
    };
    if(state.mode!=='slice'){
      months.forEach((month,index)=>{
        if(months.length>12&&index%2!==0&&month!==state.month)return;
        const pos=new THREE.Vector3((index-(months.length-1)/2)*xSpace,-2.15,3.08);
        if(state.mode==='explode')pos.x*=1.23;
        if(state.pivot)[pos.x,pos.z]=[pos.z,pos.x];
        addLabel(state.year==='all'?`${month.slice(5,7)}/${month.slice(2,4)}`:month.slice(5,7),pos,`time-label ${month===state.month?'selected-label':''}`);
      });
      const timeTitle=state.rollup?'KẾT QUẢ SQL ĐÃ ROLL-UP':months[0].slice(0,4)===months.at(-1).slice(0,4)?`THÁNG / ${months[0].slice(0,4)}`:`THÁNG / ${months[0].slice(0,4)}–${months.at(-1).slice(0,4)}`;
      const pos=new THREE.Vector3(0,2.65,0);addLabel(timeTitle,pos,'title-label');
    }else{
      const pos=new THREE.Vector3(0,2.5,0);addLabel(`LÁT ${monthName(state.month)}`,pos,'title-label');
    }
    markets.forEach((market,index)=>{
      const pos=new THREE.Vector3(state.rollup?-1.45:-4.9,(index-(markets.length-1)/2)*ySpace,state.rollup?0.8:2.75);
      if(state.mode==='slice')pos.x=-.8;
      if(state.pivot)[pos.x,pos.z]=[pos.z,pos.x];
      addLabel(market,pos,market===state.market?'selected-label':'');
    });
    products.forEach((product,index)=>{
      const productSelected=product===state.product||focusProducts.includes(product);
      if(products.length>6&&index%3!==0&&index!==products.length-1&&!productSelected)return;
      const pos=new THREE.Vector3(state.rollup?1.5:4.5,-2.08,(index-(products.length-1)/2)*zSpace);
      if(state.mode==='slice')pos.x=.95;
      if(state.pivot)[pos.x,pos.z]=[pos.z,pos.x];
      addLabel(shortName(product),pos,productSelected?'selected-label':'');
    });
    this.tooltip.hidden=true;
    if(wasEmpty)this.drawMatrices(true);
    if(state.mode==='slice'){
      this.desired.theta=state.pivot ? .14 : 1.36;
      this.desired.phi=1.18;
      this.desired.radius=12.8;
    }else if(this.lastMode==='slice')this.reset();
    this.lastMode=state.mode;
  }

  pointerMove(e){
    if(this.down){
      const dx=e.clientX-this.down.x,dy=e.clientY-this.down.y;
      if(Math.abs(dx)+Math.abs(dy)>4)this.dragged=true;
      if(this.dragged){this.canvas.classList.add('dragging');this.desired.theta=this.down.theta-dx*.007;this.desired.phi=Math.min(1.6,Math.max(.35,this.down.phi-dy*.006));}
      return;
    }
    const hit=this.hit(e);this.hoverIndex=hit;
    if(hit<0){this.tooltip.hidden=true;this.canvas.style.cursor='grab';return;}
    this.canvas.style.cursor='pointer';
    const row=this.rows[hit],rect=this.viewport.getBoundingClientRect();
    this.tooltip.replaceChildren();
    const title=document.createElement('strong');title.textContent=state.rollup?row.Market:row.Product;this.tooltip.append(title);
    const scope=document.createElement('p');scope.textContent=state.rollup?'Một dòng GROUP BY Market':`${row.Market} · ${monthName(row.MonthStart)}`;this.tooltip.append(scope);
    const values=document.createElement('p');values.textContent=state.rollup?`${row.RollupMetric} ${fmt(row.RollupValue)}`:`Sales ${fmt(row.Sales)} · Budget ${fmt(row.BudgetSales)}`;this.tooltip.append(values);
    if(!state.rollup){const gap=document.createElement('p');gap.textContent=`Gap ${row.Gap>0?'+':''}${fmt(row.Gap)}`;this.tooltip.append(gap);}
    const hint=document.createElement('small');hint.textContent=state.rollup?'Khối này tương ứng đúng một dòng SQL':'Bấm để mở lát cắt này ↗';this.tooltip.append(hint);
    this.tooltip.hidden=false;
    const tooltipWidth=this.tooltip.offsetWidth,tooltipHeight=this.tooltip.offsetHeight;
    this.tooltip.style.left=`${Math.max(8,Math.min(e.clientX-rect.left+16,rect.width-tooltipWidth-8))}px`;
    this.tooltip.style.top=`${Math.max(8,Math.min(e.clientY-rect.top-20,rect.height-tooltipHeight-10))}px`;
  }

  pointerUp(e){
    const didDrag=this.dragged;this.down=null;this.canvas.classList.remove('dragging');
    if(this.canvas.hasPointerCapture(e.pointerId))this.canvas.releasePointerCapture(e.pointerId);
    if(!didDrag){const hit=this.hit(e);if(hit>=0)this.onSelect(this.rows[hit]);}
  }

  hit(e){
    const r=this.canvas.getBoundingClientRect();
    this.pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);
    this.raycaster.setFromCamera(this.pointer,this.camera);
    const hits=this.raycaster.intersectObject(this.mesh);
    const hit=hits.find(h=>this.rows[h.instanceId]&&!this.rows[h.instanceId].hidden);
    return hit?hit.instanceId:-1;
  }

  drawMatrices(immediate=false){
    const t=immediate||reducedMotion?1:.17;
    this.rows.forEach((row,index)=>{
      row.position.lerp(row.target,t);row.currentScale.lerp(row.scale,t);row.currentColor.lerp(row.targetColor,t);
      this.matrix.position.copy(row.position);this.matrix.scale.copy(row.currentScale);this.matrix.updateMatrix();
      this.mesh.setMatrixAt(index,this.matrix.matrix);this.mesh.setColorAt(index,row.currentColor);
    });
    this.mesh.instanceMatrix.needsUpdate=true;if(this.mesh.instanceColor)this.mesh.instanceColor.needsUpdate=true;
    this.mesh.computeBoundingSphere();
    const outlineIndex=this.hoverIndex>=0?this.hoverIndex:this.selectedIndex;
    const outlined=this.rows[outlineIndex];
    this.outline.visible=Boolean(outlined&&!outlined.hidden);
    if(this.outline.visible){this.outline.position.copy(outlined.position);this.outline.scale.copy(outlined.currentScale).multiplyScalar(1.07);}
  }

  animate(now){
    requestAnimationFrame(this.animate);
    if(document.hidden||this.viewport.offsetParent===null)return;
    // Cap GPU work at ~30fps; this is an analytical scene, not a game loop.
    if(now-this.lastFrame<31)return;this.lastFrame=now;
    const smooth=reducedMotion?1:.13;
    for(const key of ['theta','phi','radius'])this.spherical[key]+=(this.desired[key]-this.spherical[key])*smooth;
    const {theta,phi,radius}=this.spherical;
    this.camera.position.set(radius*Math.sin(phi)*Math.sin(theta),radius*Math.cos(phi),radius*Math.sin(phi)*Math.cos(theta));
    this.camera.lookAt(this.cameraTarget);
    this.drawMatrices();this.renderer.render(this.scene,this.camera);
    const width=this.viewport.clientWidth,height=this.viewport.clientHeight;
    this.axes.forEach(({node,position,fixed})=>{
      if(fixed){node.style.left='50%';node.style.top='18px';node.style.visibility='visible';return;}
      const p=position.clone().project(this.camera);
      const x=(p.x*.5+.5)*width,y=(-p.y*.5+.5)*height;
      node.style.left=`${x}px`;node.style.top=`${y}px`;node.style.visibility=(p.z<1&&x>12&&x<width-12&&y>10&&y<height-38)?'visible':'hidden';
    });
  }
}
