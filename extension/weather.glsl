// Shared verbatim by Shell.GLSLEffect and tests/render_shader.py (GLSL 1.30+).
// Bounded 2-D cloud density + directional optical thickness; no raymarch or textures.
uniform vec2 u_canvas;
uniform vec4 u_view;
uniform float u_time;
uniform vec2 u_flow;
uniform float u_quality;
uniform vec3 u_color0, u_color1, u_color2, u_color3, u_color4;
uniform vec4 u_positions;
uniform float u_position4, u_stopCount;
uniform vec3 u_accent, u_glowColor;
uniform vec4 u_glow, u_celestial;
uniform float u_glowPulse, u_celestialDrift;
uniform float u_stars, u_grain, u_vignette, u_daylight;
uniform vec3 u_mesh;
uniform vec3 u_landscape;
uniform float u_coverage, u_rain, u_snow;
uniform vec2 u_wind;
// Decorative event age, fade envelope, direction and stable seed.
uniform vec4 u_leaves;
uniform vec4 u_custom;
uniform vec2 u_tint, u_surface;
uniform vec4 u_season, u_moments;
uniform vec3 u_birds;

float dwHash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
float dwNoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(dwHash(i), dwHash(i + vec2(1,0)), f.x),
        mix(dwHash(i + vec2(0,1)), dwHash(i + vec2(1,1)), f.x), f.y);
}
float dwFbm(vec2 p) {
    float n = 0.0, amplitude = 0.54;
    mat2 turn = mat2(0.83, 0.56, -0.56, 0.83);
    for (int i = 0; i < 6; i++) {
        if (float(i) >= 4.0 + u_quality) break;
        n += dwNoise(p) * amplitude;
        p = turn * p * 2.07 + vec2(11.7, 7.3);
        amplitude *= 0.48;
    }
    return n;
}
float dwBlend(float y,float a,float b) {
    float t=clamp((y-a)/max(.001,b-a),0.0,1.0);
    return t*t*(3.0-2.0*t);
}
vec3 dwPalette(float y) {
    vec3 c = mix(u_color0,u_color1,dwBlend(y,u_positions.x,u_positions.y));
    if (u_stopCount > 2.5) c=mix(c,u_color2,dwBlend(y,u_positions.y,u_positions.z));
    if (u_stopCount > 3.5) c=mix(c,u_color3,dwBlend(y,u_positions.z,u_positions.w));
    if (u_stopCount > 4.5) c=mix(c,u_color4,dwBlend(y,u_positions.w,u_position4));
    return c;
}
float dwDensity(vec2 p, float layer) {
    // Large billows retain fine turbulent detail; broad negative space at low cover.
    float n = dwFbm(p + layer*vec2(17.3,9.2));
    float threshold = mix(0.80, 0.25, u_coverage);
    return smoothstep(threshold, threshold + 0.23, n);
}
vec2 dwCloudCoords(vec2 p, float layer) {
    vec2 q=vec2(p.x,p.y*(1.1+layer*.12))*(3.0+layer*2.0);
    // All cloud motion comes from the continuous, wind-integrated flow.
    return q-u_flow*(1.0+layer*.35);
}
float dwCloudShadow(vec2 p,vec2 lightPos) {
    if(u_coverage<=.001) return 0.0;
    // Project toward the light into the same field that paints the sky.
    // Bounded soft samples approximate a cloud shadow, not a 3-D weather model.
    vec2 q=dwCloudCoords(mix(p,lightPos,.6),0.0);
    float density=dwDensity(q,0.0);
    if(u_quality>.5)
        density=(density+dwDensity(q+vec2(.10,.07),0.0))*.5;
    return density*smoothstep(0.0,.13,u_coverage);
}
float dwStars(vec2 p) {
    vec2 grid = p * 47.0;
    vec2 cell = floor(grid);
    float seed = dwHash(cell + 79.2);
    vec2 center = vec2(dwHash(cell+12.6),dwHash(cell+3.4));
    vec2 d = fract(grid)-center;
    float radius = mix(.015,.062,pow(seed,9.0));
    float star = exp(-dot(d,d)/(radius*radius));
    // Independent phases keep the field from pulsing in unison. Longer paths
    // through the atmosphere near the horizon scintillate more strongly.
    float turbulence=clamp(length(u_wind)/15.0,0.0,1.0);
    float airMass=smoothstep(.05,.9,p.y);
    float amplitude=.10+.13*airMass+.12*turbulence;
    float flicker=sin(u_time*(.7+seed*.9)+seed*129.0)*.65+
        sin(u_time*(1.9+seed*1.7)+seed*73.0)*.35;
    float sparkle=.76+amplitude*flicker;
    return star * step(1.0-u_stars/6400.0,seed) * sparkle;
}
float dwRain(vec2 p) {
    float rain = 0.0;
    for (int i=0;i<3;i++) {
        if (float(i)>u_quality+1.0) break;
        float layer = float(i);
        float scale = 56.0+layer*29.0;
        vec2 q=p*scale;
        q.x -= p.y * clamp(u_wind.x*.11,-2.0,2.0)*scale;
        q.y -= u_time*(31.0+layer*16.0);
        vec2 cell=floor(q);
        float seed=dwHash(vec2(cell.x,cell.y)+layer*27.0);
        vec2 f=fract(q);
        float streak=(1.0-smoothstep(.012,.04,abs(f.x-.5))) * smoothstep(.03,.15,f.y)*(1.0-smoothstep(.48,.96,f.y));
        rain+=streak*step(1.0-u_rain*.40,seed)*(.35+layer*.13);
    }
    return rain;
}
float dwSnow(vec2 p) {
    float snow=0.0;
    for(int i=0;i<3;i++) {
        if(float(i)>u_quality+1.0) break;
        float layer=float(i), scale=18.0+layer*16.0;
        vec2 q=p*scale;
        q.y-=u_time*(1.3+layer*.6);
        q.x+=sin(p.y*3.0+u_time*.4+layer*7.0)*.55-u_flow.x*scale*6.0;
        vec2 cell=floor(q), f=fract(q)-.5;
        float seed=dwHash(cell+layer*19.0);
        f+=vec2(sin(seed*32.0+u_time*.3),cos(seed*42.0))*.25;
        float radius=mix(.035,.13,seed)/(1.0+layer*.25);
        snow+=exp(-dot(f,f)/(radius*radius))*step(1.0-u_snow*.48,seed)*(.7-layer*.12);
    }
    return snow;
}
vec3 dwLeaves(vec3 sky, vec2 p) {
    float age=u_leaves.x, direction=u_leaves.z;
    float aspect=u_canvas.x/max(1.0,u_canvas.y);
    float across=direction>0.0 ? p.x/aspect : 1.0-p.x/aspect;
    float front=min(1.2,age*.18);
    float source=1.0-smoothstep(front,front+.18,across);
    // Two bounded depth layers; no per-leaf actors, textures or particle uploads.
    for(int i=0;i<2;i++) {
        float layer=float(i), scale=mix(6.5,3.8,layer);
        vec2 travel=vec2(direction*(age*.22+.02*sin(age*1.1)),age*.07);
        vec2 q=(p-travel)*scale;
        vec2 cell=floor(q);
        float seed=dwHash(cell+vec2(u_leaves.w,layer*23.7));
        if(seed < mix(.77,.65,layer)) continue;
        vec2 f=fract(q)-.5;
        f-=vec2(sin(seed*45.0+age*1.7),cos(seed*27.0+age*.9))*.09;
        // Reject empty pixels before the shape, rotation and vein calculations.
        if(max(abs(f.x),abs(f.y))>.3) continue;
        float angle=seed*31.4+age*(1.1+seed*.9);
        float c=cos(angle),s=sin(angle);
        vec2 leaf=mat2(c,-s,s,c)*f;
        leaf.x/= .38+.62*abs(cos(age*2.1+seed*17.0));
        float theta=atan(leaf.y,leaf.x);
        float lobes=1.0-abs(fract(theta*(5.0/6.283185)+.5)*2.0-1.0);
        float radius=.065+.065*lobes+.012*sin(theta);
        float aa=max(.001,scale/u_canvas.y*.8);
        float body=1.0-smoothstep(radius-aa,radius+aa,length(leaf));
        float stem=(1.0-smoothstep(.006,.006+aa,abs(leaf.x))) *
            smoothstep(.07,.085,leaf.y)*(1.0-smoothstep(.18,.19,leaf.y));
        float veins=(1.0-smoothstep(.002,.002+aa,abs(leaf.x)))+
            (1.0-smoothstep(.002,.002+aa,abs(abs(leaf.x)*.65-abs(leaf.y+.02))))*.45;
        vec3 gold=vec3(.91,.55,.08),rust=vec3(.64,.18,.045),red=vec3(.70,.27,.09);
        vec3 pigment=mix(gold,mix(rust,red,seed),smoothstep(.78,1.0,seed));
        pigment*= (.78+.22*cos(angle))*(.35+.65*u_daylight);
        pigment=mix(pigment,pigment*.48,clamp(veins,0.0,1.0)*body*.5);
        sky=mix(sky,pigment,max(body,stem*.8)*u_leaves.y*source*mix(.62,.96,layer));
    }
    return sky;
}
float dwRidge(float x,float layer,float height,float style) {
    float relief=1.0+u_custom.y;
    if(style>1.5 && style<2.5) {
        float peaks=abs(dwNoise(vec2(x*3.5,layer*7.0+3.0))-.5)*.19+
            dwNoise(vec2(x*11.0,layer*13.0))*.035+
            dwNoise(vec2(x*37.0,layer*19.0))*.012;
        return 1.0-height+layer*.065+
            (peaks-.065+sin(x*19.0+layer)*.004)*height/.2*relief;
    }
    if(style>2.5) return 1.0-height+layer*.055+
        (sin(x*1.7+layer*1.8)*.035+sin(x*3.1+layer)*.015)*height/.2*relief;
    return 1.0-height+layer*.055+
        (sin(x*2.0+layer*2.0)*.045+sin(x*5.3+layer*3.0)*.018+
         sin(x*11.0+layer)*.006)*height/.2*relief;
}
vec3 dwOcean(vec3 sky,vec2 p,vec3 terrain,vec2 lightPos) {
    float horizon=1.0-terrain.y;
    if(p.y<horizon) return sky;
    float depth=clamp((p.y-horizon)/terrain.y,0.0,1.0);
    // Long, broken glints on a perspective-compressed water surface. Integrated
    // weather flow keeps wave advection continuous when the wind changes.
    float travel=u_time*(1.0+length(u_wind)*.025);
    float perspective=1.0/(depth+.065);
    float ripple=sin(perspective*5.0-travel*1.4+
        sin(p.x*18.0-u_flow.x*20.0+travel*.17)*2.0+u_flow.y*35.0);
    ripple=ripple*.65+.35*sin(perspective*8.7-travel*.83+p.x*29.0);
    float detail=dwNoise(vec2(p.x*95.0,perspective*17.0-travel*.7)-u_flow*9.0);
    vec3 reflected=dwPalette(clamp(horizon-(p.y-horizon)*1.5,0.0,1.0));
    vec3 water=mix(reflected,u_color0*.26+u_color1*.22,.45+depth*.28);
    water*=.9+.1*ripple;
    float width=.016+depth*.20;
    float reflection=exp(-pow((p.x-lightPos.x+sin(p.y*210.0)*width*.25)/width,2.0));
    float glint=smoothstep(.25,.95,ripple*.5+detail*.5);
    water+=mix(vec3(.55,.67,.78),u_glowColor,u_daylight)*reflection*glint*
        (.10+u_daylight*.20)*(1.0-u_coverage*.7);
    water=mix(water,u_color4*(.38+.62*u_daylight),exp(-depth*34.0)*.35);
    return mix(sky,water,smoothstep(horizon,horizon+1.0/u_canvas.y,p.y));
}
vec3 dwLandscape(vec3 sky,vec2 p,vec3 terrain,vec2 lightPos) {
    float height=terrain.y, mist=terrain.z;
    if(terrain.x>3.5) return dwOcean(sky,p,terrain,lightPos);
    if(p.y < 1.0-height-.08*(1.0+u_custom.y)) return sky;
    vec3 shadow=u_color0*.22+u_color1*.15;
    vec3 horizon=u_color4*mix(.38,1.0,u_daylight);
    float cloudShadow=dwCloudShadow(p,lightPos)*mix(.12,.45,u_daylight);
    float aa=max(.0005,1.0/u_canvas.y);
    for(int i=0;i<3;i++) {
        float layer=float(i);
        float ridge=dwRidge(p.x,layer,height,terrain.x);
        if(i==2 && terrain.x<1.5) {
            // A distant, irregular treeline, fixed to the landscape, not the wind.
            float grove=smoothstep(.25,.65,dwNoise(vec2(p.x*4.0,17.3)));
            ridge-=dwNoise(vec2(p.x*85.0,7.9))*.021*grove;
        }
        float fog=(.6-layer*.23)*(.65+mist*.7);
        // Slower, depth-separated ground wisps use the same wind as the clouds.
        // Their strength is art direction; it does not claim measured fog.
        if(mist>.001) {
            vec2 mistPoint=vec2(p.x*(2.8+layer),p.y*(12.0-layer*2.0));
            float wisp=dwNoise(mistPoint-u_flow*(.6+layer*.25)+layer*8.7);
            fog+=mist*.15*(1.0-layer*.3)*smoothstep(.35,.75,wisp);
        }
        float slope=(cos(p.x*2.0+layer*2.0)*.09+
            cos(p.x*5.3+layer*3.0)*.0954+cos(p.x*11.0+layer)*.066)*height/.2;
        if(terrain.x>1.5) {
            // Spread the normal over a small face area, avoiding vertical
            // lighting stripes at the mathematical cusp of a distant peak.
            float faceX=p.x+(p.y-ridge)*.55;
            slope=(dwRidge(faceX+.025,layer,height,terrain.x)-
                dwRidge(faceX-.025,layer,height,terrain.x))/.05;
        }
        vec2 normal=normalize(vec2(-slope,-1.0));
        vec2 lightDirection=normalize(lightPos-vec2(p.x,ridge)+vec2(.001,-.001));
        float diffuse=max(0.0,dot(normal,lightDirection));
        vec3 ground=shadow*(.76+.24*diffuse)*(1.0-cloudShadow);
        vec3 pigment=mix(ground,horizon,fog);
        if(terrain.x>1.5 && terrain.x<2.5) {
            // Altitude-shaped snowline, cut by exposed rock; mountain faces
            // inherit the same sun direction and cloud shadows as the hills.
            float snowline=1.0-height+.025+layer*.065+sin(p.x*31.0)*.007;
            float snow=(1.0-smoothstep(snowline-.008,snowline+.008,p.y));
            vec3 snowColor=mix(u_color2,u_color4,.68)*(.45+.55*u_daylight);
            snowColor*= (.72+.28*diffuse)*(1.0-cloudShadow*.65);
            pigment=mix(pigment,snowColor,snow*.9);
            float rock=dwNoise(vec2(p.x*170.0,p.y*260.0)+layer*31.0);
            float gullies=dwNoise(vec2((p.x+(p.y-ridge)*.45)*85.0,p.y*20.0));
            pigment*=.65+.23*diffuse+.18*rock+.18*gullies;
        } else if(terrain.x>2.5) {
            vec3 sand=mix(u_color4,vec3(.78,.46,.22),.38)*(.22+.58*u_daylight);
            pigment=mix(pigment,sand,.42)*( .8+.2*diffuse);
            float crest=exp(-max(0.0,p.y-ridge)*170.0);
            pigment+=u_color4*crest*(.03+.08*u_daylight);
            float ripples=sin(p.y*900.0+sin(p.x*3.0)*8.0)*.012;
            pigment+=ripples*u_daylight*smoothstep(ridge+.015,ridge+.1,p.y);
        }
        pigment+=u_accent*.015*(1.0-layer*.3)*u_daylight;
        float silhouette=smoothstep(ridge-aa,ridge+aa,p.y);
        sky=mix(sky,pigment,silhouette);
    }
    return sky;
}
float dwLivingSegment(vec2 p,vec2 a,vec2 b) {
 vec2 v=b-a;return length(p-a-v*clamp(dot(p-a,v)/max(dot(v,v),.0000001),0.0,1.0));
}
float dwLivingRidge(vec2 p,vec3 terrain) {
 if(terrain.x>3.5)return 1.0-terrain.y;
 return min(dwRidge(p.x,0.0,terrain.y,terrain.x),min(dwRidge(p.x,1.0,terrain.y,terrain.x),dwRidge(p.x,2.0,terrain.y,terrain.x)));
}
vec3 dwLivingSurface(vec3 sky,vec2 p,vec3 terrain) {
 if(terrain.x<.5)return sky;
 float ridge=dwLivingRidge(p,terrain),ground=smoothstep(ridge-.002,ridge+.004,p.y),wet=clamp(u_surface.y,0.0,1.0)*ground;
 sky*=1.0-wet*.25;
 float patch=smoothstep(.68,.86,dwNoise(vec2(p.x*21.0,p.y*135.0)))*wet;
 patch*=smoothstep(ridge+.025,ridge+.10,p.y);
 float ripple=.92+.08*sin(p.x*115.0+p.y*240.0+u_time*.7);
 vec3 reflected=mix(u_color3,u_color4,.55)*(.66+.34*u_daylight);
 sky=mix(sky,reflected*ripple,patch*.45);
 float snow=clamp(u_surface.x,0.0,1.0),settled=smoothstep(.58,.92,dwNoise(p*vec2(60.0,95.0))+snow*.68);
 vec3 snowColor=mix(vec3(.22,.29,.40),vec3(.88,.93,.95),u_daylight);
 return mix(sky,snowColor,ground*snow*settled*.93);
}
vec3 dwLivingSeason(vec3 sky,vec2 p,vec3 terrain) {
 if(terrain.x<.5||terrain.x>2.5)return sky;
 float ridge=dwLivingRidge(p,terrain),ground=smoothstep(ridge,ridge+.008,p.y);
 vec3 tint=vec3(1.0)+u_season.x*vec3(-.07,-.02,.08)+u_season.y*vec3(-.03,.07,-.02)+u_season.w*vec3(.13,-.01,-.10);
 sky=mix(sky,sky*tint,ground*.65);
 float cell=floor(p.x*18.0),seed=dwHash(vec2(cell,71.3)),center=(cell+.3+seed*.35)/18.0;
 if(seed<.35)return sky;
 float base=dwRidge(center,1.0,terrain.y,terrain.x)+.025,height=.035+seed*.035,width=.0008+seed*.0004;
 vec2 a=vec2(center,base),top=vec2(center,base-height);
 float branch=dwLivingSegment(p,a,top);
 branch=min(branch,dwLivingSegment(p,vec2(center,base-height*.43),vec2(center-.014,base-height*.79)));
 branch=min(branch,dwLivingSegment(p,vec2(center,base-height*.56),vec2(center+.013,base-height*.88)));
 float wood=1.0-smoothstep(width,width+.0011,branch);
 vec3 woodColor=mix(vec3(.025,.035,.05),vec3(.16,.15,.12),u_daylight);
 sky=mix(sky,woodColor,wood*.83);
 float foliage=clamp(u_season.y*.78+u_season.z+u_season.w*.45,0.0,1.0);
 vec2 canopy=(p-vec2(center,base-height*.83))/vec2(.018,height*.39);
 float leaf=1.0-smoothstep(.72,1.08,length(canopy));
 leaf*=smoothstep(.12,.55,dwNoise(p*160.0)+foliage*.45)*foliage;
 vec3 leafColor=vec3(.20,.34,.19)*u_season.y+vec3(.12,.25,.17)*u_season.z+vec3(.49,.25,.11)*u_season.w;
 leafColor*=.35+.65*u_daylight;
 return mix(sky,leafColor,leaf*.86);
}
vec3 dwLivingMoments(vec3 sky,vec2 p) {
 float aspect=u_canvas.x/max(1.0,u_canvas.y),phase=clamp(u_birds.y,0.0,1.0),seed=u_birds.z;
 if(u_moments.x>.001) {
  vec2 head=vec2((.18+seed*.35+phase*.32)*aspect,.11+seed*.10+phase*.14),tail=head-vec2(.13,.045);
  float streak=exp(-pow(dwLivingSegment(p,tail,head)/.0012,2.0)),nucleus=exp(-dot(p-head,p-head)/.000006);
  sky+=vec3(.70,.80,1.0)*(streak*.65+nucleus)*u_moments.x;
 }
 if(u_moments.y>.001) {
  float center=(.28+seed*.46)*aspect,zig=center+sin(floor(p.y*27.0)*13.7+seed*21.0)*.013;
  float bolt=(1.0-smoothstep(.0008,.002,abs(p.x-zig)))*smoothstep(.29,.32,p.y)*(1.0-smoothstep(.70,.75,p.y));
  sky+=vec3(.55,.58,.72)*bolt*u_moments.y+vec3(.045,.05,.075)*u_moments.y*(1.0-smoothstep(.75,1.0,p.y));
 }
 if(u_moments.z>.001||u_moments.w>.001) {
  for(int i=0;i<8;i++) {
   float fi=float(i),r=dwHash(vec2(fi+seed*10.0,53.4));
   vec2 pos=vec2((.08+r*.84)*aspect,.64+dwHash(vec2(fi,19.1))*.27);
   pos+=vec2(sin(u_time*.33+fi)*.012,cos(u_time*.24+fi*2.1)*.009);
   float glow=exp(-dot(p-pos,p-pos)/.000009),pulse=.55+.45*sin(u_time*1.2+fi*3.7);
   sky+=vec3(.50,.67,.15)*glow*pulse*u_moments.z;
   vec2 pollen=vec2(fract(r+u_time*.007+phase*.03)*aspect,.42+dwHash(vec2(fi,37.2))*.48);
   float dust=exp(-dot(p-pollen,p-pollen)/.000004);sky+=vec3(.43,.35,.17)*dust*u_moments.w;
  }
 }
 if(u_birds.x>.001) {
  for(int i=0;i<3;i++) {
   float fi=float(i);vec2 center=vec2((.12+phase*.70)*aspect-fi*.035,.31+seed*.1+fi*.018);
   float flap=sin(u_time*2.8+fi)*.005,distance=dwLivingSegment(p,center-vec2(.011,.004+flap),center);
   distance=min(distance,dwLivingSegment(p,center,center+vec2(.011,-.004-flap)));
   float bird=1.0-smoothstep(.0007,.0018,distance);sky=mix(sky,vec3(.035,.045,.055),bird*u_birds.x*.85);
  }
 }
 return sky;
}

vec3 dynwall(vec2 localUV) {
    vec2 uv=(u_view.xy+localUV*u_view.zw)/u_canvas;
    float aspect=u_canvas.x/u_canvas.y;
    vec2 p=vec2(uv.x*aspect,uv.y);
    // Cached pre-landscape controllers omit this uniform (all zeroes). New
    // controllers always supply a valid height, including when switched off.
    vec3 terrain=u_landscape.y==0.0 ? vec3(1.0,.2,.5) : u_landscape;
    if(dot(abs(u_custom.xyz),vec3(1.0))>.000001) {
        // Horizon and terrain relief are independent physical controls.
        terrain.y=clamp(terrain.y-u_custom.x,.08,.45);
        terrain.z=clamp(terrain.z+u_custom.z,0.0,1.0);
    }
    float visibleHorizon=clamp(1.0-terrain.y,.1,.98);
    vec3 sky=dwPalette(clamp(uv.y/visibleHorizon,0.0,1.0));
    float luminance=dot(u_color0,vec3(.2126,.7152,.0722));
    float daylight=u_daylight;
    sky*=mix(mix(.17,1.0,1.0-smoothstep(.06,.28,luminance)),1.0,daylight);
    vec2 sun=vec2(u_celestial.x*aspect,u_celestial.y);
    sun.x+=sin(u_time*.012)*u_celestialDrift*aspect;
    vec2 lightPos=u_celestial.w>.5 ? sun : vec2(u_glow.x*aspect,u_glow.y);
    float distanceToLight=length(p-lightPos);
    vec2 glowPos=vec2(u_glow.x*aspect,u_glow.y);
    float glow=exp(-dot(p-glowPos,p-glowPos)/(u_glow.z*u_glow.z*.24));
    sky=mix(sky,u_glowColor,glow*u_glow.w*.44*(1.0+sin(u_time*.18)*u_glowPulse));
    if(u_stars != 0.0) sky+=vec3(.76,.84,1.0)*dwStars(p)*(1.0-daylight*.92);
    if(u_celestial.w>.5) {
        float radius=u_celestial.z;
        float aa=max(.0006,1.0/u_canvas.y);
        float disk=1.0-smoothstep(radius-aa,radius+aa,length(p-sun));
        vec3 discColor=u_celestial.w>1.5 ? vec3(.81,.87,.94) : vec3(1.0,.94,.77);
        if(u_celestial.w>1.5) {
            float crater=dwNoise((p-sun)*140.0)*dwNoise((p-sun)*73.0+12.0);
            discColor*=.77+.23*crater;
            float sphere=sqrt(max(0.0,1.0-distanceToLight*distanceToLight/(radius*radius)));
            discColor*=.82+.18*sphere;
        } else {
            float core=clamp(1.0-distanceToLight/radius,0.0,1.0);
            discColor=mix(vec3(1.0,.73,.39),vec3(1.0,.96,.81),pow(core,.3));
        }
        float aureole=exp(-distanceToLight*distanceToLight/(radius*radius*65.0));
        sky=mix(sky,mix(discColor,u_glowColor,.25),aureole*(u_celestial.w>1.5?.035:.10));
        sky+=discColor*exp(-distanceToLight*distanceToLight/(radius*radius*7.0))*.17;
        sky=mix(sky,discColor,disk*.96);
    }
    // Composite from far to near. Stars and moon are underneath every cloud layer.
    if(u_coverage>.001) {
        for(int i=0;i<3;i++) {
            if(float(i)>u_quality) break;
            float layer=float(i);
            vec2 q=dwCloudCoords(p,layer);
            float density=dwDensity(q,layer);
            vec2 lightDirection=normalize(lightPos-p+vec2(.01,-.1));
            float toward=dwDensity(q+lightDirection*.055,layer);
            float edge=clamp((density-toward)*3.2,-.5,1.0);
            float optical=density*(3.4+layer*.45);
            float alpha=(1.0-exp(-optical))*smoothstep(0.0,.13,u_coverage);
            vec3 shadow=mix(u_color1*.53,vec3(.43,.49,.56),daylight*.45);
            vec3 lit=mix(vec3(.17,.23,.33),mix(vec3(.96,.96,.91),u_glowColor,u_glow.w*.28),daylight);
            float lighting=clamp(.72+edge*.25-density*.20,0.0,1.0);
            vec3 cloud=mix(shadow,lit,lighting);
            float silver=pow(max(edge,0.0),2.0)*exp(-distanceToLight*1.0);
            cloud+=mix(vec3(.33,.43,.62),mix(vec3(1.0,.86,.65),u_glowColor,.35),daylight)*silver*.12;
            // Thin cloud edges softly scatter the art-directed glow color.
            cloud+=u_glowColor*glow*u_glow.w*.12*(1.0-density);
            sky=mix(sky,cloud,alpha);
        }
    }
    float haze=smoothstep(visibleHorizon*.55,visibleHorizon,uv.y)*(.035+u_coverage*.13);
    vec3 horizonLight=mix(u_color4,u_glowColor,u_glow.w*.12)*mix(.38,1.0,daylight);
    sky=mix(sky,horizonLight,haze);
    if(terrain.x>.5) sky=dwLandscape(sky,p,terrain,lightPos);
    if(dot(u_surface,u_surface)>.000001) sky=dwLivingSurface(sky,p,terrain);
    if(dot(u_season,u_season)>.000001) sky=dwLivingSeason(sky,p,terrain);
    if(dot(u_moments,u_moments)+u_birds.x*u_birds.x>.000001) sky=dwLivingMoments(sky,p);
    if(u_rain>.001) sky+=vec3(.58,.67,.75)*dwRain(p)*.56;
    if(u_snow>.001) sky=mix(sky,vec3(.91,.95,1.0),clamp(dwSnow(p),0.0,.9));
    if(u_mesh.x>.5) {
        vec2 q=p*u_mesh.y;
        vec2 cell=floor(q); vec2 f=fract(q);
        float facet=dwHash(cell+step(f.y,f.x));
        float lines=1.0-smoothstep(.008,.025,min(min(f.x,f.y),abs(f.x-f.y)));
        float amount=u_mesh.x>1.5 ? lines*.28 : (facet-.5)*.32;
        sky+=u_accent*amount*u_mesh.z;
    }
    if(dot(abs(u_tint),vec2(1.0))>.000001)
        sky=sky*(1.0-u_tint.y*.65)+vec3(u_tint.x*.07,0.0,-u_tint.x*.07);
    vec2 vignette=uv-.5;
    if(u_leaves.y>.001 && terrain.x<2.5) sky=dwLeaves(sky,p);
    sky*=1.0-u_vignette*min(1.0,dot(vignette,vignette)*1.3)*.6;
    if(u_grain != 0.0) sky+=(dwHash(floor(p*u_canvas.y)+floor(u_time*30.0))-.5)*u_grain*.48;
    return clamp(sky,0.0,1.0);
}
