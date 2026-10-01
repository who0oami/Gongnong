const COUNT=57,PREFIX="NIA_SL_WORD1202_SYN03_F_";
const video=document.querySelector("#sourceVideo"),overlay=document.querySelector("#overlay"),ctx=overlay.getContext("2d"),statusEl=document.querySelector("#status"),frameEl=document.querySelector("#frameNo"),retargetEl=document.querySelector("#retarget"),faceEl=document.querySelector("#showFace");
let frames=[],avatar,last=-1;
const pts=a=>{const r=[];for(let i=0;i<a.length;i+=3)r.push({x:a[i],y:a[i+1],c:a[i+2]});return r};
const good=(...p)=>p.every(v=>v&&v.c>.12&&v.x&&v.y);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
const angle=(a,b,c)=>{const u={x:a.x-b.x,y:a.y-b.y},v={x:c.x-b.x,y:c.y-b.y};return Math.atan2(u.x*v.y-u.y*v.x,u.x*v.x+u.y*v.y)};
const direction=(a,b)=>Math.atan2(b.y-a.y,b.x-a.x);

async function loadFrames(){frames=await Promise.all(Array.from({length:COUNT},(_,i)=>fetch(`sample/keypoints/${PREFIX}${String(i).padStart(12,"0")}_keypoints.json`).then(r=>{if(!r.ok)throw Error(`키포인트 ${i} 로드 실패`);return r.json()})))}
function chain(p,indexes,color,r=3){ctx.strokeStyle=ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();let on=false;for(const i of indexes){const v=p[i];if(!v||v.c<.12){on=false;continue}on?ctx.lineTo(v.x,v.y):ctx.moveTo(v.x,v.y);on=true}ctx.stroke();for(const i of indexes){const v=p[i];if(v&&v.c>=.12){ctx.beginPath();ctx.arc(v.x,v.y,r,0,Math.PI*2);ctx.fill()}}}
function draw(f){const p=f.people,pose=pts(p.pose_keypoints_2d),lh=pts(p.hand_left_keypoints_2d),rh=pts(p.hand_right_keypoints_2d),fc=pts(p.face_keypoints_2d);ctx.clearRect(0,0,overlay.width,overlay.height);ctx.save();ctx.scale(overlay.width/video.videoWidth,overlay.height/video.videoHeight);[[1,2,3,4],[1,5,6,7],[2,5],[0,1]].forEach(c=>chain(pose,c,"#4dd8ff",5));const hands=[[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]];hands.forEach(c=>chain(lh,c,"#ffd54a"));hands.forEach(c=>chain(rh,c,"#ff6687"));[[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],[17,18,19,20,21],[22,23,24,25,26],[36,37,38,39,40,41,36],[42,43,44,45,46,47,42],[48,49,50,51,52,53,54,55,56,57,58,59,48],[60,61,62,63,64,65,66,67,60]].forEach(c=>chain(fc,c,"#8eff9b",2));ctx.restore()}
function resize(){const b=video.getBoundingClientRect();overlay.width=Math.max(1,Math.round(b.width*devicePixelRatio));overlay.height=Math.max(1,Math.round(b.height*devicePixelRatio));overlay.style.width=b.width+"px";overlay.style.height=b.height+"px"}
function frameIndex(){return video.duration&&isFinite(video.duration)?clamp(Math.round(video.currentTime/video.duration*(COUNT-1)),0,COUNT-1):0}
function tick(){const i=frameIndex();if(frames[i]&&i!==last){draw(frames[i]);if(avatar&&retargetEl.checked)avatar.apply(frames[i]);frameEl.textContent=i;last=i}requestAnimationFrame(tick)}

const canvas=document.querySelector("#renderCanvas"),engine=new BABYLON.Engine(canvas,true);
async function createScene(){const scene=new BABYLON.Scene(engine);scene.clearColor=new BABYLON.Color4(.035,.045,.065,1);const camera=new BABYLON.ArcRotateCamera("camera",Math.PI/2,Math.PI/2.08,2.35,new BABYLON.Vector3(0,1.18,0),scene);camera.attachControl(canvas,true);camera.lowerRadiusLimit=1.4;camera.upperRadiusLimit=4;new BABYLON.HemisphericLight("light",new BABYLON.Vector3(.2,1,-.5),scene).intensity=1.35;
 const imported=await BABYLON.SceneLoader.ImportMeshAsync("","./models/","ksl_avatar.glb",scene),root=imported.meshes[0],bounds=root.getHierarchyBoundingVectors(true);root.position.y-=bounds.min.y;
 const nodes=new Map(scene.transformNodes.map(n=>[n.name,n])),bases=new Map();nodes.forEach((n,name)=>{if(name.startsWith("J_Bip_")){if(!n.rotationQuaternion)n.rotationQuaternion=BABYLON.Quaternion.FromEulerVector(n.rotation);bases.set(name,n.rotationQuaternion.clone())}});
 const morphs=new Map();scene.meshes.forEach(m=>{const x=m.morphTargetManager;if(x)for(let i=0;i<x.numTargets;i++)morphs.set(x.getTarget(i).name,x.getTarget(i))});
 const rotateZ=(name,r)=>{const n=nodes.get(name),q=bases.get(name);if(n&&q)n.rotationQuaternion=q.multiply(BABYLON.Quaternion.RotationAxis(BABYLON.Axis.Z,r))};
 const reset=()=>{bases.forEach((q,n)=>nodes.get(n).rotationQuaternion=q.clone());morphs.forEach(m=>m.influence=0)};
 // 영상 좌표는 Y가 아래로 증가한다. 모델의 T-pose 기준각은 왼팔=PI, 오른팔=0이다.
 // 상완은 절대 방향, 하완은 상완에 대한 상대 방향으로 계산해야 부모 회전이 중복되지 않는다.
 const arm=(p,s)=>{const left=s==="L",a=p[left?5:2],b=p[left?6:3],c=p[left?7:4];if(!good(a,b,c))return;const upperScreen=direction(a,b),lowerScreen=direction(b,c),restWorld=left?Math.PI:0;rotateZ(`J_Bip_${s}_UpperArm`,wrap(-upperScreen-restWorld));rotateZ(`J_Bip_${s}_LowerArm`,wrap(-(lowerScreen-upperScreen)))};
 const fingerMap=[["Thumb",[1,2,3,4]],["Index",[5,6,7,8]],["Middle",[9,10,11,12]],["Ring",[13,14,15,16]],["Little",[17,18,19,20]]];
 const hand=(values,s)=>{const h=pts(values),mirror=s==="L"?-1:1;for(const [name,c] of fingerMap)for(let j=1;j<=3;j++){const a=h[c[j-1]],b=h[c[j]],d=h[c[Math.min(j+1,3)]];if(good(a,b,d))rotateZ(`J_Bip_${s}_${name}${j}`,mirror*clamp(Math.PI-Math.abs(angle(a,b,d)),0,2.2))}};
 const setMorph=(n,v)=>{const m=morphs.get(n);if(m)m.influence=clamp(v,0,1)};
 const face=values=>{morphs.forEach(m=>m.influence=0);if(!faceEl.checked)return;const f=pts(values),width=good(f[0],f[16])?Math.hypot(f[0].x-f[16].x,f[0].y-f[16].y):1,ratio=(a,b)=>good(a,b)?Math.hypot(a.x-b.x,a.y-b.y)/width:0;setMorph("Fcl_EYE_Close_L",(.018-ratio(f[37],f[41]))*70);setMorph("Fcl_EYE_Close_R",(.018-ratio(f[43],f[47]))*70);setMorph("Fcl_MTH_A",(ratio(f[62],f[66])-.012)*14);setMorph("Fcl_MTH_Large",(ratio(f[62],f[66])-.025)*8)};
 avatar={reset,apply(f){reset();const p=f.people,pose=pts(p.pose_keypoints_2d);arm(pose,"L");arm(pose,"R");hand(p.hand_left_keypoints_2d,"L");hand(p.hand_right_keypoints_2d,"R");face(p.face_keypoints_2d)}};
 document.querySelector("#reset").onclick=()=>{retargetEl.checked=false;reset()};retargetEl.onchange=()=>{last=-1;if(!retargetEl.checked)reset()};faceEl.onchange=()=>last=-1;return scene}
Promise.all([loadFrames(),createScene()]).then(([,scene])=>{statusEl.textContent="준비 완료 — 영상을 재생하세요";statusEl.classList.add("ready");engine.runRenderLoop(()=>scene.render());last=-1;tick()}).catch(e=>{console.error(e);statusEl.textContent="오류: "+e.message;statusEl.classList.add("error")});
video.addEventListener("loadedmetadata",resize);window.addEventListener("resize",()=>{engine.resize();resize();last=-1});
