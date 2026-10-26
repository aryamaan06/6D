/* Local 3D stainless-steel companion: procedural mesh/materials, no downloads.
 * Lighting uses vertex normals; exhaust is a time-varying transparent 3D mesh.
 * This decorative rendering is not a propulsion/flight simulation. */
(() => {
  'use strict';
  const VERTEX=`attribute vec3 aPosition;attribute vec3 aNormal;
    uniform mat4 uModel;uniform mat4 uProjection;uniform mediump float uMaterial;uniform mediump float uTime;
    varying vec3 vPosition;varying vec3 vNormal;varying vec3 vLocal;
    void main(){vec3 source=aPosition;if(uMaterial>1.5){float flow=clamp((-source.y-1.54)/1.72,0.,1.);source.x+=.035*flow*sin(source.y*15.+uTime*10.);source.z+=.025*flow*cos(source.y*13.+uTime*8.);}vec4 p=uModel*vec4(source,1.);vLocal=source;
      vPosition=p.xyz;vNormal=mat3(uModel)*aNormal;gl_Position=uProjection*p;}`;
  const FRAGMENT=`precision mediump float;
    varying vec3 vPosition;varying vec3 vNormal;varying vec3 vLocal;
    uniform vec3 uColor;uniform mediump float uMaterial;uniform mediump float uTime;
    float noise(vec3 p){return sin(p.x*17.4+sin(p.y*13.2-p.z*8.1))*sin(p.z*21.2+p.y*6.4);}
    void main(){
      vec3 n=normalize(vNormal);vec3 eye=normalize(vec3(0.,0.,9.)-vPosition);
      if(uMaterial>1.5){
        float flow=clamp((-vLocal.y-1.54)/1.72,0.,1.);
        float twist=noise(vec3(vLocal.x*3.,vLocal.y*4.+uTime*7.,vLocal.z*3.));
        float diamonds=pow(.5+.5*sin(flow*36.-uTime*10.),5.);
        float rim=pow(abs(dot(n,eye)),.6);
        float fade=pow(1.-flow,.85);
        vec3 hot=mix(vec3(.05,.25,1.),vec3(1.,.32,.035),smoothstep(.18,.82,flow));
        hot=mix(hot,vec3(1.,.98,.90),clamp(.14-flow*.10+diamonds*.48,0.,.7));
        float alpha=(.52+.25*rim+.15*diamonds+twist*.09)*fade;
        gl_FragColor=vec4(hot,alpha);return;
      }
      vec3 light=normalize(vec3(-3.,5.,7.));
      float diffuse=max(dot(n,light),0.);
      float spec=pow(max(dot(n,normalize(light+eye)),0.),uMaterial>.5?24.:105.);
      float fresnel=pow(1.-max(dot(n,eye),0.),3.);
      vec3 r=reflect(-eye,n);
      vec3 env=mix(vec3(.13,.18,.22),vec3(.79,.85,.91),smoothstep(-.40,.65,r.y));
      float strip=pow(max(0.,1.-abs(r.x+.3)*2.),12.);
      env+=vec3(.65,.70,.72)*strip;
      float seam=1.-.15*pow(.5+.5*cos((vLocal.y+1.6)*30.),32.);
      float grain=noise(vLocal*vec3(80.,7.,80.))*.016;
      vec3 steel=(uColor*(.20+.45*diffuse)+env*.53+vec3(spec*.82)+fresnel*.14)*seam+grain;
      if(uMaterial>.5)steel=uColor*(.38+.55*diffuse)+vec3(spec*.20)+fresnel*.08;
      gl_FragColor=vec4(clamp(steel,0.,1.),1.);
    }`;
  const identity=()=>new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
  function multiply(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
  function rotation(axis,a){const m=identity(),c=Math.cos(a),s=Math.sin(a);if(axis==='x'){m[5]=c;m[6]=s;m[9]=-s;m[10]=c;}if(axis==='y'){m[0]=c;m[2]=-s;m[8]=s;m[10]=c;}if(axis==='z'){m[0]=c;m[1]=s;m[4]=-s;m[5]=c;}return m;}
  function projection(aspect){const m=identity(),half=3.15;m[0]=1/(half*aspect);m[5]=1/half;m[10]=-.08;m[13]=.10;return m;}
  function mesh(){return {positions:[],normals:[]};}
  function triangle(out,a,b,c,normal){
    if(!normal){const u=b.map((v,i)=>v-a[i]),v=c.map((x,i)=>x-a[i]);normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];const length=Math.hypot(...normal)||1;normal=normal.map(x=>x/length);}
    out.positions.push(...a,...b,...c);out.normals.push(...normal,...normal,...normal);
  }
  function lathe(profile,segments=64,offset=[0,0,0]){
    const out=mesh();
    for(let j=0;j<profile.length-1;j++){
      const [y0,r0]=profile[j],[y1,r1]=profile[j+1],slope=(r0-r1)/(y1-y0||1);
      for(let k=0;k<segments;k++){
        const t0=k*2*Math.PI/segments,t1=(k+1)*2*Math.PI/segments;
        const point=(y,r,t)=>[r*Math.cos(t)+offset[0],y+offset[1],r*Math.sin(t)+offset[2]];
        const p0=point(y0,r0,t0),p1=point(y0,r0,t1),p2=point(y1,r1,t1),p3=point(y1,r1,t0);
        for(const group of [[p0,p1,p2],[p0,p2,p3]]){
          out.positions.push(...group.flat());
          for(const p of group){const angle=Math.atan2(p[2]-offset[2],p[0]-offset[0]),length=Math.hypot(1,slope);out.normals.push(Math.cos(angle)/length,slope/length,Math.sin(angle)/length);}
        }
      }
    }
    return out;
  }
  function fin(angle,front=false){
    const out=mesh(),y=front?.98:-1.13,w=front?.64:.92;
    const points=[[.33,y-.38,-.035],[w,y-.68,-.035],[w-.1,y+.12,-.035],[.32,y+.58,-.035]];
    const rotate=p=>[p[0]*Math.cos(angle)-p[2]*Math.sin(angle),p[1],p[0]*Math.sin(angle)+p[2]*Math.cos(angle)];
    const back=points.map(p=>[p[0],p[1],.035]);const a=points.map(rotate),b=back.map(rotate);
    triangle(out,a[0],a[1],a[2]);triangle(out,a[0],a[2],a[3]);triangle(out,b[2],b[1],b[0]);triangle(out,b[3],b[2],b[0]);
    for(let i=0;i<4;i++){const next=(i+1)%4;triangle(out,a[i],b[i],b[next]);triangle(out,a[i],b[next],a[next]);}
    return out;
  }
  function mount(canvas){
    const media=matchMedia('(prefers-reduced-motion: reduce)');let reduced=media.matches,visible=true,paused=false,disposed=false,frame=0,last=0,count=0;
    let gl,program,drawables=[];
    const fallback=()=>{canvas.dataset.renderer='fallback';canvas.dataset.motion=reduced?'reduced':'paused';canvas.hidden=true;canvas.parentElement?.classList.add('sd-rocket-fallback-visible');};
    try{
      gl=canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:false,preserveDrawingBuffer:true,powerPreference:'low-power'});
      if(!gl)throw Error('WebGL unavailable');
      const shader=(type,text)=>{const result=gl.createShader(type);gl.shaderSource(result,text);gl.compileShader(result);if(!gl.getShaderParameter(result,gl.COMPILE_STATUS))throw Error('Decorative shader unavailable');return result;};
      program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,VERTEX));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,FRAGMENT));gl.linkProgram(program);
      if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Decorative program unavailable');
      gl.useProgram(program);
      const add=(shape,color,material=0)=>{
        const buffer=(values)=>{const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);return b;};
        drawables.push({p:buffer(shape.positions),n:buffer(shape.normals),count:shape.positions.length/3,color,material});
      };
      add(lathe([[-1.52,.31],[-1.47,.36],[.98,.36],[1.25,.34],[1.50,.29],[1.72,.21],[1.93,.10],[2.06,0]]),[.64,.68,.70]);
      for(const angle of [.2,Math.PI+.2]){add(fin(angle),[.40,.44,.47]);add(fin(angle,true),[.44,.48,.51]);}
      add(lathe([[-1.54,.32],[-1.50,.35],[-1.41,.35]]),[.08,.10,.12],1);
      for(const [x,z] of [[-.12,.08],[.12,.08],[0,-.12]])add(lathe([[-1.67,.105],[-1.60,.095],[-1.46,.04]],32,[x,0,z]),[.18,.20,.23],1);
      add(lathe([[-1.64,.21],[-1.92,.22],[-2.13,.15],[-2.39,.20],[-2.67,.13],[-3.05,.025]],40),[1,1,1],2);
      const attributes=['aPosition','aNormal'].map(name=>gl.getAttribLocation(program,name));
      const uniforms=Object.fromEntries(['uModel','uProjection','uColor','uMaterial','uTime'].map(name=>[name,gl.getUniformLocation(program,name)]));
      function draw(time=0){
        if(disposed||!canvas.isConnected)return;
        const width=Math.max(1,Math.round(canvas.clientWidth*Math.min(devicePixelRatio||1,2))),height=Math.max(1,Math.round(canvas.clientHeight*Math.min(devicePixelRatio||1,2)));
        if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
        gl.viewport(0,0,width,height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.depthMask(true);gl.disable(gl.BLEND);
        const model=multiply(rotation('z',-.40),multiply(rotation('y',.62),rotation('x',.16)));
        gl.uniformMatrix4fv(uniforms.uModel,false,model);gl.uniformMatrix4fv(uniforms.uProjection,false,projection(width/height));gl.uniform1f(uniforms.uTime,reduced?0:time*.001);
        for(const part of drawables){
          if(part.material===2){gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);}
          for(let i=0;i<2;i++){gl.bindBuffer(gl.ARRAY_BUFFER,i===0?part.p:part.n);gl.vertexAttribPointer(attributes[i],3,gl.FLOAT,false,0,0);gl.enableVertexAttribArray(attributes[i]);}
          gl.uniform3fv(uniforms.uColor,part.color);gl.uniform1f(uniforms.uMaterial,part.material);gl.drawArrays(gl.TRIANGLES,0,part.count);
        }
        gl.depthMask(true);canvas.dataset.frameCount=String(++count);
      }
      function tick(time){frame=0;if(disposed||reduced||paused||document.hidden||!visible)return;if(time-last>=33){draw(time);last=time;}frame=requestAnimationFrame(tick);}
      function refresh(){cancelAnimationFrame(frame);frame=0;canvas.dataset.motion=reduced?'reduced':paused||document.hidden||!visible?'paused':'running';draw(performance.now());if(!reduced&&!paused&&!document.hidden&&visible)frame=requestAnimationFrame(tick);}
      canvas.dataset.renderer='webgl';canvas.hidden=false;
      const onMedia=event=>{reduced=event.matches;refresh();},onVisibility=()=>refresh();
      media.addEventListener('change',onMedia);document.addEventListener('visibilitychange',onVisibility);
      const observer=typeof IntersectionObserver==='function'?new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting!==false;refresh();}):null;observer?.observe(canvas);
      const onLost=event=>{event.preventDefault();cancelAnimationFrame(frame);fallback();};canvas.addEventListener('webglcontextlost',onLost);
      refresh();return {renderer:'webgl',setPaused(value){paused=!!value;refresh();},dispose(){disposed=true;cancelAnimationFrame(frame);observer?.disconnect();media.removeEventListener('change',onMedia);document.removeEventListener('visibilitychange',onVisibility);canvas.removeEventListener('webglcontextlost',onLost);for(const part of drawables){gl.deleteBuffer(part.p);gl.deleteBuffer(part.n);}gl.deleteProgram(program);}};
    }catch{fallback();return {renderer:'fallback',dispose(){disposed=true;cancelAnimationFrame(frame);}};}
  }
  window.SixDRocketRenderer=Object.freeze({mount});
})();
