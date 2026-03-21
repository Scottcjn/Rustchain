// ─── DATA ─────────────────────────────────────────────────────────────────────
var RC={Validator:'#58a6ff',Navigator:'#3b82f6',Sensor:'#06b6d4',Miner:'#f59e0b',Attestor:'#22c55e',Collector:'#84cc16',Coordinator:'#a855f7',Listener:'#ec4899',Beacon:'#f97316',Wizard:'#8b5cf6',Phantom:'#6b7280',Builder:'#14b8a6',Linker:'#0ea5e9'};
var PCT={infrastructure:'#f0883e',compute:'#fb923c',storage:'#fbbf24',sensor:'#a3e635',communication:'#4ade80',gateway:'#2dd4bf',workshop:'#2dd4bf'};
var LC={heartbeat:'#3b82f6',contract:'#22c55e',mayday:'#ef4444',owns:'#f0883e'};

var CIT=[
  {id:'city-alpha',name:'City Alpha',color:'#3b82f6'},
  {id:'city-beta', name:'City Beta', color:'#22c55e'},
  {id:'city-gamma',name:'City Gamma',color:'#f59e0b'},
  {id:'city-delta',name:'City Delta',color:'#a855f7'}
];

var AGS=[
  {id:'sophia-core', name:'Sophia Core',  city:'city-alpha',role:'Validator',  activity:95,wallet:'RTC2f8…9f4e',power:87,properties:3},
  {id:'atlas-nav',   name:'Atlas Nav',    city:'city-alpha',role:'Navigator',  activity:78,wallet:'RTC3a1…2b7c',power:62,properties:1},
  {id:'hex-audio',   name:'Hex Audio',    city:'city-alpha',role:'Sensor',     activity:45,wallet:'RTC4c2…3d8e',power:41,properties:2},
  {id:'miner-x',     name:'Miner X',      city:'city-alpha',role:'Miner',      activity:99,wallet:'RTC5d3…4e9f',power:99,properties:5},
  {id:'glassworm',   name:'Glassworm',    city:'city-beta', role:'Attestor',  activity:88,wallet:'RTC6e4…5fa0',power:72,properties:2},
  {id:'vintage-bot', name:'Vintage Bot', city:'city-beta', role:'Collector',  activity:67,wallet:'RTC7f5…6ab1',power:55,properties:4},
  {id:'neon-flash',  name:'Neon Flash',  city:'city-beta', role:'Sensor',    activity:34,wallet:'RTC8a6…7bc2',power:28,properties:1},
  {id:'atlas-prime', name:'Atlas Prime',  city:'city-gamma',role:'Coordinator',activity:92,wallet:'RTC9b7…8cd3',power:81,properties:3},
  {id:'rust-echo',   name:'Rust Echo',    city:'city-gamma',role:'Listener',  activity:56,wallet:'RTCac8…9de4',power:48,properties:2},
  {id:'pulse-agent', name:'Pulse Agent', city:'city-gamma',role:'Beacon',    activity:73,wallet:'RTCbd9…aef5',power:64,properties:1},
  {id:'wizard-chain',name:'Wizard Chain', city:'city-gamma',role:'Wizard',    activity:61,wallet:'RTCce0…bf06',power:53,properties:2},
  {id:'echo-miner',  name:'Echo Miner',   city:'city-delta',role:'Miner',    activity:85,wallet:'RTCdf1…c017',power:78,properties:4},
  {id:'nexus-seven', name:'Nexus Seven',  city:'city-delta',role:'Linker',   activity:70,wallet:'RTCe02…d128',power:59,properties:1},
  {id:'ghost-signal',name:'Ghost Signal',city:'city-delta',role:'Phantom',   activity:29,wallet:'RTCf13…e239',power:22,properties:0},
  {id:'forge-run',   name:'Forge Run',   city:'city-alpha',role:'Builder',   activity:82,wallet:'RTC024…f34a',power:69,properties:3}
];

var PROPS=[
  {id:'prop-001',name:'Server Rack Alpha-7',    city:'city-alpha',agent:'sophia-core', type:'infrastructure',valuation:45000},
  {id:'prop-002',name:'GPU Cluster Node 3',      city:'city-alpha',agent:'miner-x',     type:'compute',        valuation:120000},
  {id:'prop-003',name:'Storage Array Beta-2',  city:'city-alpha',agent:'atlas-nav',   type:'storage',        valuation:23000},
  {id:'prop-004',name:'Validator Node V-12',    city:'city-beta', agent:'glassworm',   type:'infrastructure',valuation:67000},
  {id:'prop-005',name:'Collector Vault C-4',    city:'city-beta', agent:'vintage-bot', type:'storage',        valuation:89000},
  {id:'prop-006',name:'Sensor Hub S-8',         city:'city-beta', agent:'neon-flash',  type:'sensor',         valuation:12000},
  {id:'prop-007',name:'Coordination Center G-1', city:'city-gamma',agent:'atlas-prime',type:'infrastructure',valuation:156000},
  {id:'prop-008',name:'Listener Array L-9',    city:'city-gamma',agent:'rust-echo',   type:'sensor',         valuation:31000},
  {id:'prop-009',name:'Beacon Tower B-3',       city:'city-gamma',agent:'pulse-agent',type:'communication',  valuation:54000},
  {id:'prop-010',name:'Miner Farm Delta-5',    city:'city-delta',agent:'echo-miner', type:'compute',        valuation:210000},
  {id:'prop-011',name:'Link Node LN-11',        city:'city-delta',agent:'nexus-seven',type:'infrastructure',valuation:28000},
  {id:'prop-012',name:'Builder Workshop W-6',    city:'city-alpha',agent:'forge-run',   type:'workshop',       valuation:41000},
  {id:'prop-013',name:'Antique Server Farm',    city:'city-beta', agent:'vintage-bot', type:'compute',        valuation:78000},
  {id:'prop-014',name:'AltiVec Cluster AV-1',  city:'city-alpha',agent:'sophia-core', type:'compute',       valuation:95000},
  {id:'prop-015',name:'Web3 Gateway GW-2',      city:'city-gamma',agent:'wizard-chain',type:'gateway',      valuation:67000}
];

var CONNS=[
  {s:'sophia-core',t:'atlas-nav',  ty:'heartbeat',str:.9,lat:12},{s:'atlas-nav',t:'hex-audio',  ty:'heartbeat',str:.7,lat:23},
  {s:'sophia-core',t:'glassworm', ty:'heartbeat',str:.8,lat:31},{s:'glassworm',t:'vintage-bot',ty:'heartbeat',str:.85,lat:18},
  {s:'atlas-prime',t:'rust-echo', ty:'heartbeat',str:.75,lat:9 },{s:'atlas-prime',t:'pulse-agent',ty:'heartbeat',str:.92,lat:7},
  {s:'echo-miner', t:'nexus-seven',ty:'heartbeat',str:.6,lat:41},{s:'miner-x',t:'forge-run',  ty:'heartbeat',str:.88,lat:15},
  {s:'sophia-core',t:'miner-x',  ty:'heartbeat',str:.95,lat:5 },{s:'glassworm',t:'neon-flash',ty:'heartbeat',str:.5,lat:55},
  {s:'sophia-core',t:'glassworm', ty:'contract', str:.7,val:5000},{s:'atlas-prime',t:'atlas-nav', ty:'contract',str:.6,val:3200},
  {s:'miner-x',    t:'echo-miner',ty:'contract', str:.8,val:8500},{s:'vintage-bot',t:'sophia-core',ty:'contract',str:.65,val:2100},
  {s:'forge-run',  t:'atlas-prime',ty:'contract',str:.55,val:1800},{s:'wizard-chain',t:'pulse-agent',ty:'contract',str:.7,val:4200},
  {s:'rust-echo',  t:'nexus-seven',ty:'contract',str:.5,val:900},
  {s:'ghost-signal',t:'sophia-core',ty:'mayday',str:.4,urg:'high'},{s:'neon-flash',t:'glassworm',ty:'mayday',str:.6,urg:'medium'},
  {s:'ghost-signal',t:'nexus-seven',ty:'mayday',str:.3,urg:'low'},
  {s:'sophia-core',t:'prop-001',ty:'owns'},{s:'sophia-core',t:'prop-014',ty:'owns'},{s:'miner-x',t:'prop-002',ty:'owns'},
  {s:'atlas-nav',  t:'prop-003',ty:'owns'},{s:'glassworm',t:'prop-004',ty:'owns'},{s:'vintage-bot',t:'prop-005',ty:'owns'},
  {s:'vintage-bot',t:'prop-013',ty:'owns'},{s:'atlas-prime',t:'prop-007',ty:'owns'},{s:'rust-echo',t:'prop-008',ty:'owns'},
  {s:'pulse-agent',t:'prop-009',ty:'owns'},{s:'echo-miner',t:'prop-010',ty:'owns'},{s:'nexus-seven',t:'prop-011',ty:'owns'},
  {s:'forge-run',  t:'prop-012',ty:'owns'},{s:'wizard-chain',t:'prop-015',ty:'owns'}
];

// ─── BUILD GRAPH ─────────────────────────────────────────────────────────────
var W=window.innerWidth,HH=window.innerHeight-56;
var cpos=[{c:CIT[0],x:W*.25,y:HH*.35},{c:CIT[1],x:W*.75,y:HH*.25},{c:CIT[2],x:W*.5,y:HH*.65},{c:CIT[3],x:W*.15,y:HH*.7}];
cpos.forEach(function(p){p.c.x=p.x;p.c.y=p.y;});

var ND=[],LK=[];
cpos.forEach(function(p){ND.push({id:p.c.id,name:p.c.name,type:'city',x:p.x,y:p.y,fx:p.x,fy:p.y,color:p.c.color,r:38});});
AGS.forEach(function(a){
  ND.push({id:a.id,name:a.name,type:'agent',role:a.role,city:a.city,activity:a.activity,wallet:a.wallet,power:a.power,properties:a.properties,color:RC[a.role]||'#8b949e',r:5+(a.activity/100)*13});
});
PROPS.forEach(function(p){
  ND.push({id:p.id,name:p.name,type:'property',propertyType:p.type,valuation:p.valuation,city:p.city,owner:p.agent,color:PCT[p.type]||'#f0883e',r:4+(p.valuation/10000)*6});
});
CONNS.forEach(function(c){LK.push({s:c.s,t:c.t,ty:c.ty,str:c.str||1,lat:c.lat,val:c.val,urg:c.urg});});

// Update stats
document.getElementById('sa').textContent=AGS.length;
document.getElementById('sp').textContent=PROPS.length;
document.getElementById('sc2').textContent=CONNS.length;
document.getElementById('scit').textContent=CIT.length;
document.getElementById('sb-a').textContent=AGS.length;
document.getElementById('sb-p').textContent=PROPS.length;
document.getElementById('sb-c').textContent=CONNS.length;

// ─── RENDER ─────────────────────────────────────────────────────────────────
var svg=d3.select('#g').attr('width',W).attr('height',HH);
var defs=svg.append('defs');
[['blue','#3b82f6'],['green','#22c55e'],['red','#ef4444'],['orange','#f0883e']].forEach(function(d){
  defs.append('marker').attr('id','a-'+d[0]).attr('viewBox','0 -4 8 8').attr('refX',12).attr('refY',0).attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto')
    .append('path').attr('d','M0,-4L8,0L0,4').attr('fill',d[1]);
});

var g=svg.append('g');
svg.call(d3.zoom().scaleExtent([.1,4]).on('zoom',function(e){g.attr('transform',e.transform);}));

var ln=g.append('g').selectAll('line').data(LK).join('line')
  .attr('stroke',function(d){return LC[d.ty];})
  .attr('stroke-opacity',function(d){return d.ty==='owns'?0.22:0.55;})
  .attr('stroke-width',function(d){return d.ty==='owns'?1:1+d.str*2;})
  .attr('marker-end',function(d){
    if(d.ty==='owns')return '';
    var m=d.ty==='heartbeat'?'blue':d.ty==='contract'?'green':d.ty==='mayday'?'red':'orange';
    return 'url(#a-'+m+')';
  })
  .attr('stroke-dasharray',function(d){return d.ty==='mayday'?'4,3':d.ty==='contract'?'6,2':'none';});

var nd=g.append('g').selectAll('g').data(ND).join('g')
  .attr('cursor','pointer')
  .call(d3.drag().on('start',function(e,d){if(!d.fx){d.fx=d.x;d.fy=d.y;}}).on('drag',function(e,d){d.fx=e.x;d.fy=e.y;}).on('end',function(e,d){if(d.type!=='city'){d.fx=null;d.fy=null;}}))
  .on('click',function(e,d){showD(d);})
  .on('mouseover',function(e,d){showT(e,d);})
  .on('mouseout',function(){document.getElementById('tip').classList.remove('on');});

nd.filter(function(d){return d.type==='city';}).append('circle').attr('r',function(d){return d.r+12;}).attr('fill','none').attr('stroke',function(d){return d.color;}).attr('stroke-width',2).attr('stroke-opacity',.35).attr('stroke-dasharray','5,4');
nd.filter(function(d){return d.type==='city';}).append('text').text(function(d){return d.name;}).attr('text-anchor','middle').attr('dy',function(d){return d.r+26;}).attr('fill',function(d){return d.color;}).attr('font-size','12px').attr('font-weight','600');
nd.filter(function(d){return d.type==='city';}).append('text').attr('class','cc').attr('text-anchor','middle').attr('dy',5).attr('fill',function(d){return d.color;}).attr('font-size','16px').attr('font-weight','700');
nd.filter(function(d){return d.type!=='city';}).append('circle').attr('r',function(d){return d.r;}).attr('fill',function(d){return d.color;}).attr('fill-opacity',.88).attr('stroke',function(d){return d3.color(d.color).brighter(.4);}).attr('stroke-width',1.5);
nd.filter(function(d){return d.type!=='city';}).append('text').text(function(d){return d.name.length>11?d.name.slice(0,10)+'…':d.name;}).attr('text-anchor','middle').attr('dy',function(d){return d.r+11;}).attr('fill','#8b949e').attr('font-size','9px');
nd.filter(function(d){return d.type==='agent'&&d.activity>80;}).insert('circle',':first-child').attr('r',function(d){return d.r+5;}).attr('fill','none').attr('stroke',function(d){return d.color;}).attr('stroke-width',1).attr('stroke-opacity',.3);

var sim=d3.forceSimulation(ND)
  .force('link',d3.forceLink(LK).id(function(n){return n.id;}).distance(function(d){return d.ty==='owns'?70:110;}).strength(function(d){return d.str*0.4;}))
  .force('charge',d3.forceManyBody().strength(-250))
  .force('center',d3.forceCenter(W/2,HH/2).strength(.03))
  .force('collide',d3.forceCollide().radius(function(d){return d.r+6;})))
  .on('tick',function(){
    ln.attr('x1',function(d){return d.s.x;}).attr('y1',function(d){return d.s.y;}).attr('x2',function(d){return d.t.x;}).attr('y2',function(d){return d.t.y;});
    nd.attr('transform',function(d){return 'translate('+d.x+','+d.y+')';});
    nd.filter(function(d){return d.type==='city';}).select('.cc').text(function(d){return AGS.filter(function(a){return a.city===d.id;}).length;});
  });

// ─── INTERACTIVITY ────────────────────────────────────────────────────────────
var af='all',cc=null,st='';
function fl(){
  nd.style('opacity',function(d){
    if(d.type==='city')return 1;
    if(st&&!d.name.toLowerCase().includes(st.toLowerCase())&&!(d.role||'').toLowerCase().includes(st.toLowerCase()))return 0.08;
    if(af==='city'&&d.type==='agent')return d.city===cc?1:0.08;
    return 1;
  });
  ln.style('opacity',function(d){return d.ty==='owns'?0.12:0.45;});
}
nd.filter(function(d){return d.type==='city';}).on('click',function(e,d){
  cc=cc===d.id?null:d.id;af=cc?'city':'all';
  document.querySelectorAll('.b').forEach(function(x){x.classList.remove('a');});
  document.querySelector('[data-f="'+af+'"]').classList.add('a');
  fl();
});
document.querySelectorAll('.b').forEach(function(b){b.addEventListener('click',function(){
  af=b.dataset.f;cc=null;
  document.querySelectorAll('.b').forEach(function(x){x.classList.remove('a');});
  b.classList.add('a');
  fl();
});});
document.getElementById('sr').addEventListener('input',function(e){st=e.target.value;fl();});

// ─── TOOLTIP ─────────────────────────────────────────────────────────────────
function showT(e,d){
  var tip=document.getElementById('tip');
  tip.classList.add('on');
  document.getElementById('tt').textContent=d.name;
  var h='';
  if(d.type==='city'){
    var ag=AGS.filter(function(a){return a.city===d.id;});
    h='<div class="tr"><span class="tl">Agents</span><span class="tv">'+ag.length+'</span></div>';
    h+='<div class="tr"><span class="tl">Roles</span><span class="tv">'+[...new Set(ag.map(function(a){return a.role;}))].join(', ')+'</span></div>';
    h+='<div class="tr"><span class="tl">Avg activity</span><span class="tv">'+Math.round(ag.reduce(function(s,a){return s+a.activity;},0)/ag.length)+'%</span></div>';
    h+='<div class="tr"><span class="tl">Total power</span><span class="tv">'+ag.reduce(function(s,a){return s+a.power;},0)+'</span></div>';
  }else if(d.type==='agent'){
    h='<div class="tr"><span class="tl">Role</span><span class="tv">'+d.role+'</span></div>';
    h+='<div class="tr"><span class="tl">Activity</span><span class="tv">'+d.activity+'%</span></div>';
    h+='<div class="tr"><span class="tl">Power</span><span class="tv">'+d.power+'</span></div>';
    h+='<div class="tr"><span class="tl">Properties</span><span class="tv">'+d.properties+'</span></div>';
    h+='<div class="tr"><span class="tl">Wallet</span><span class="tv">'+d.wallet+'</span></div>';
  }else{
    h='<div class="tr"><span class="tl">Type</span><span class="tv">'+d.propertyType+'</span></div>';
    h+='<div class="tr"><span class="tl">Valuation</span><span class="tv">'+d.valuation.toLocaleString()+' RTC</span></div>';
    h+='<div class="tr"><span class="tl">Owner</span><span class="tv">'+d.owner+'</span></div>';
  }
  document.getElementById('tb').innerHTML=h;
  var tx=e.clientX+16,ty=e.clientY-10;
  if(tx+290>window.innerWidth)tx=e.clientX-296;
  if(ty+200>window.innerHeight)ty=e.clientY-200;
  tip.style.left=tx+'px';tip.style.top=ty+'px';
}

// ─── SIDEBAR ─────────────────────────────────────────────────────────────────
function showD(d){
  var sb=document.getElementById('sb'),sc=document.getElementById('sc');
  sb.classList.add('on');
  if(d.type==='city'){
    var ag=AGS.filter(function(a){return a.city===d.id;});
    var pr=PROPS.filter(function(p){return p.city===d.id;});
    var may=CONNS.filter(function(c){return c.ty==='mayday'&&(c.s===d.id||c.t===d.id);});
    var html='<div class="dr"><label>City</label><value>'+d.name+'</value></div><hr class="sep">';
    html+='<div class="dr"><label>Total Agents</label><value>'+ag.length+'</value></div>';
    html+='<div class="dr"><label>Total Properties</label><value>'+pr.length+'</value></div>';
    html+='<div class="dr"><label>Combined Valuation</label><value>'+pr.reduce(function(s,p){return s+p.valuation;},0).toLocaleString()+' RTC</value></div>';
    html+='<div class="dr"><label>Mayday Signals</label><value>'+may.length+'</value></div>';
    html+='<hr class="sep"><div class="dr"><label>Agents</label></div>';
    ag.forEach(function(a){
      html+='<div style="margin:4px 0 4px 8px;padding-left:8px;border-left:2px solid '+(RC[a.role]||'#8b949e')+'">';
      html+='<value>'+a.name+'</value><br>';
      html+='<span class="bdg bdg-r">'+a.role+'</span> Activity:'+a.activity+'% Power:'+a.power+'</div>';
    });
    sc.innerHTML=html;
  }else if(d.type==='agent'){
    var pr=PROPS.filter(function(p){return p.agent===d.id;});
    var hbs=CONNS.filter(function(c){return c.ty==='heartbeat'&&(c.s===d.id||c.t===d.id);});
    var cts=CONNS.filter(function(c){return c.ty==='contract'&&(c.s===d.id||c.t===d.id);});
    var may=CONNS.filter(function(c){return c.ty==='mayday'&&(c.s===d.id||c.t===d.id);});
    var html='<div class="dr"><label>Agent</label><value>'+d.name+'</value></div>';
    html+='<div class="dr"><label>Role</label><value><span class="bdg bdg-r">'+d.role+'</span></value></div>';
    html+='<div class="dr"><label>Activity</label><value>'+d.activity+'%</value></div>';
    html+='<div class="dr"><label>Power Score</label><value>'+d.power+'</value></div>';
    html+='<div class="dr"><label>Wallet</label><value style="font-family:\'Courier New\',monospace;font-size:11px">'+d.wallet+'</value></div>';
    html+='<hr class="sep">';
    html+='<div class="dr"><label>Properties ('+pr.length+')</label><value>Total: '+pr.reduce(function(s,p){return s+p.valuation;},0).toLocaleString()+' RTC</value></div>';
    pr.forEach(function(p){
      html+='<div style="margin:3px 0 3px 8px;padding-left:8px;border-left:2px solid #f0883e">';
      html+='<value>'+p.name+'</value><br>';
      html+='<span class="bdg bdg-t">'+p.propertyType+'</span> '+p.valuation.toLocaleString()+' RTC</div>';
    });
    html+='<hr class="sep">';
    html+='<div class="dr"><label>Heartbeat Links</label><value>'+hbs.length+'</value></div>';
    html+='<div class="dr"><label>Contract Links</label><value>'+cts.length+' ('+cts.reduce(function(s,c){return s+(c.val||0);},0).toLocaleString()+' RTC)</value></div>';
    html+='<div class="dr"><label>Mayday Signals</label><value>'+may.length+'</value></div>';
    may.forEach(function(m){
      var urg=m.urg||'?';
      var cls=urg==='high'?'bdg-h':urg==='medium'?'bdg-m':'bdg-l';
      html+='<div style="margin:2px 0 2px 8px"><span class="bdg '+cls+'">'+urg+'</span> urgency &rarr; '+(m.s===d.id?m.t:m.s)+'</div>';
    });
    sc.innerHTML=html;
  }else{
    var own=AGS.find(function(a){return a.id===d.owner;});
    var links=CONNS.filter(function(c){return c.t===d.id||c.s===d.id;});
    var html='<div class="dr"><label>Property</label><value>'+d.name+'</value></div>';
    html+='<div class="dr"><label>Type</label><value><span class="bdg bdg-t">'+d.propertyType+'</span></value></div>';
    html+='<div class="dr"><label>Valuation</label><value>'+d.valuation.toLocaleString()+' RTC</value></div>';
    html+='<div class="dr"><label>Owner</label><value>'+d.owner+(own?' <span class="bdg bdg-r">'+own.role+'</span>':'')+'</value></div>';
    html+='<hr class="sep">';
    html+='<div class="dr"><label>Connections</label><value>'+links.length+'</value></div>';
    links.filter(function(l){return l.ty!=='owns';}).forEach(function(l){
      var other=l.s===d.id?l.t:l.s;
      var cls=l.ty==='heartbeat'?'bdg bdg-r':l.ty==='contract'?'bdg bdg-t':'bdg bdg-h';
      var info='';
      if(l.lat)info=' ('+l.lat+'ms)';
      if(l.val)info=' ('+l.val.toLocaleString()+' RTC)';
      html+='<div style="margin:2px 0 2px 8px"><span class="'+cls+'">'+l.ty+'</span> &rarr; '+other+info+'</div>';
    });
    sc.innerHTML=html;
  }
}
