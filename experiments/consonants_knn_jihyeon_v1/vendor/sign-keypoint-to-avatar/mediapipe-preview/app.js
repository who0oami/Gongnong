/* MediaPipe Tasks schema only. Rest directions come from the loaded avatar. */
'use strict';
const $ = id => document.getElementById(id);
const video = $('video'), overlay = $('overlay'), ctx = overlay.getContext('2d');
let data, profile, scene, engine, rigs = [], last = -1, videoUrl;
const V = (...args) => new BABYLON.Vector3(...args);
const good = p => p && [p.x,p.y,p.z].every(Number.isFinite);
const point = p => V(p.x * profile.axis[0], p.y * profile.axis[1], p.z * profile.axis[2]);
const fail = error => { console.error(error); $('status').textContent = '오류: ' + error.message; };
async function json(url) {const r = await fetch(url); if (!r.ok) throw Error(`${url}: ${r.status}`); return r.json();}
function validate(d) {
  if(d.schema !== 'mediapipe-holistic-v1' || !d.frames?.length || d.frame_count !== d.frames.length || !(d.fps>0)) throw Error('MediaPipe Holistic JSON이 필요합니다.');
  let prev = -1;
  for(const f of d.frames) {
    if(!Number.isFinite(f.time) || f.time <= prev) throw Error('프레임 시간이 올바르지 않습니다.');
    prev=f.time;
    for(const [key,n] of [['pose',33],['pose_world',33],['left_hand',21],['right_hand',21],['left_hand_world',21],['right_hand_world',21]])
      if(!Array.isArray(f[key]) || ![0,n].includes(f[key].length) || !f[key].every(good)) throw Error(`잘못된 좌표: ${key}`);
  }
  return d;
}
function setData(d) { data=validate(d); $('seek').max=data.frames.length-1; last=-1; $('status').textContent=`${d.label || d.sign_id} · ${d.frame_count} 프레임 · ${d.fps.toFixed(2)} FPS`; }
function fromTo(a,b) {
  a=a.normalizeToNew(); b=b.normalizeToNew();
  const dot=BABYLON.Vector3.Dot(a,b);
  if(dot < -.999999) {
    let axis=BABYLON.Vector3.Cross(a,BABYLON.Axis.X);
    if(axis.lengthSquared()<1e-8) axis=BABYLON.Vector3.Cross(a,BABYLON.Axis.Y);
    return BABYLON.Quaternion.RotationAxis(axis.normalize(),Math.PI);
  }
  const c=BABYLON.Vector3.Cross(a,b);
  return new BABYLON.Quaternion(c.x,c.y,c.z,1+dot).normalize();
}
function aim(rig,index,direction) {
  if(direction.lengthSquared()<1e-10) return;
  const n=rig.nodes[index];
  const inv=n.parent ? n.parent.computeWorldMatrix(true).clone().invert() : BABYLON.Matrix.Identity();
  const local=BABYLON.Vector3.TransformNormal(direction,inv).normalize();
  n.rotationQuaternion=fromTo(rig.restDirections[index],local).multiply(rig.base[index]);
  n.computeWorldMatrix(true);
}
function apply(f) {
  for(const rig of rigs) {
    // Reset per frame: seeking and missing observations must not retain stale poses.
    rig.nodes.slice(0,3).forEach((n,i)=>{n.rotationQuaternion=rig.base[i].clone();n.computeWorldMatrix(true);});
    const p=rig.spec.pose.map(i=>f.pose_world[i]);
    const visible=rig.spec.pose.map(i=>f.pose[i]);
    if(!p.every(good) || !visible.every(v=>good(v) && (v.visibility ?? 1)>=profile.min_visibility)) continue;
    aim(rig,0,point(p[1]).subtract(point(p[0])));
    aim(rig,1,point(p[2]).subtract(point(p[1])));
    const h=f[rig.spec.hand+'_world'];
    // Hand origin is separate from pose origin. Only within-hand directions are used.
    if(good(h[0]) && good(h[9])) aim(rig,2,point(h[9]).subtract(point(h[0])));
  }
}
function draw(f) {
  overlay.width=overlay.clientWidth*devicePixelRatio; overlay.height=overlay.clientHeight*devicePixelRatio;
  const w=video.videoWidth || data.width,h=video.videoHeight || data.height;
  const scale=Math.min(overlay.width/w,overlay.height/h),ox=(overlay.width-w*scale)/2,oy=(overlay.height-h*scale)/2;
  function chain(p,ids,color) {
    ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2*devicePixelRatio;ctx.beginPath();let on=false;
    for(const i of ids){const v=p[i];if(!good(v)||(v.visibility??1)<.5){on=false;continue;}const x=ox+v.x*w*scale,y=oy+v.y*h*scale;on?ctx.lineTo(x,y):ctx.moveTo(x,y);on=true;}
    ctx.stroke();for(const i of ids){const v=p[i];if(!good(v)||(v.visibility??1)<.5)continue;ctx.beginPath();ctx.arc(ox+v.x*w*scale,oy+v.y*h*scale,3*devicePixelRatio,0,Math.PI*2);ctx.fill();}
  }
  [[11,13,15],[12,14,16],[11,12]].forEach(c=>chain(f.pose,c,'#63d9ff'));
  for(const [key,color] of [['left_hand','#ffd666'],['right_hand','#ff7caa']])
    [[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]].forEach(c=>chain(f[key],c,color));
}
function indexAt(time){let lo=0,hi=data.frames.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(data.frames[m].time<=time+.0005)lo=m;else hi=m-1;}return lo;}
function show(i){apply(data.frames[i]);draw(data.frames[i]);$('seek').value=i;$('frame').textContent=`${i} / ${data.frames.length-1}`;last=i;}
async function init() {
  [profile,data]=await Promise.all([json('profile.json'),json('../keypoints/love.json')]);validate(data);
  const source=await fetch('assets/love.mp4');if(!source.ok)throw Error('영상 로드 실패');
  videoUrl=URL.createObjectURL(await source.blob());video.src=videoUrl;
  engine=new BABYLON.Engine($('render'),true);scene=new BABYLON.Scene(engine);scene.useRightHandedSystem=true;
  scene.clearColor=new BABYLON.Color4(.035,.05,.075,1);
  const camera=new BABYLON.ArcRotateCamera('camera',Math.PI/2,Math.PI/2.1,2.1,V(0,1.25,0),scene);camera.attachControl($('render'),true);
  new BABYLON.HemisphericLight('light',V(0,1,-1),scene).intensity=1.5;
  await BABYLON.SceneLoader.ImportMeshAsync('', '', profile.model,scene);
  scene.animationGroups.forEach(g=>g.stop());
  const nodes=new Map(scene.transformNodes.map(n=>[n.name,n]));
  for(const spec of Object.values(profile.sides)) {
    const ns=spec.bones.map(name=>{if(!nodes.has(name))throw Error(`모델에 관절이 없습니다: ${name}`);return nodes.get(name);});
    const base=ns.slice(0,3).map(n=>(n.rotationQuaternion || BABYLON.Quaternion.FromEulerVector(n.rotation)).clone());
    const restDirections=ns.slice(0,3).map((n,i)=>{
      n.computeWorldMatrix(true);ns[i+1].computeWorldMatrix(true);
      const delta=ns[i+1].getAbsolutePosition().subtract(n.getAbsolutePosition());
      const inv=n.parent?n.parent.computeWorldMatrix(true).clone().invert():BABYLON.Matrix.Identity();
      return BABYLON.Vector3.TransformNormal(delta,inv).normalize();
    });
    rigs.push({nodes:ns,base,restDirections,spec});
  }
  setData(data);
  engine.runRenderLoop(()=>{const i=indexAt(video.currentTime);if(i!==last)show(i);scene.render();});
  window.preview={showFrame:show,scene,rigs,get data(){return data;}};
}
$('play').onclick=()=>video.paused?video.play().catch(fail):video.pause();
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','BUTTON','VIDEO'].includes(e.target.tagName)){e.preventDefault();$('play').click();}});
$('seek').oninput=()=>{if(!data)return;video.pause();const i=Number($('seek').value);video.currentTime=data.frames[i].time;show(i);};
$('jsonFile').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;video.pause();setData(JSON.parse(await file.text()));video.currentTime=0;}catch(error){fail(error);}};
$('videoFile').onchange=e=>{const f=e.target.files[0];if(!f)return;if(videoUrl)URL.revokeObjectURL(videoUrl);videoUrl=URL.createObjectURL(f);video.src=videoUrl;last=-1;};
window.addEventListener('resize',()=>{engine?.resize();last=-1;});
init().catch(fail);
