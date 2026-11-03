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
        float peaks=abs(dwNoise(vec2(x*3.5,layer*7.0+3.0))-.5)*.21+
            abs(dwNoise(vec2(x*9.0,layer*13.0))-.5)*.054+
            dwNoise(vec2(x*37.0,layer*19.0))*.009;
        return 1.0-height+layer*.065+
            (peaks-.065+sin(x*19.0+layer)*.004)*height/.2*relief;
    }
    if(style>2.5) return 1.0-height+layer*.055+
        (sin(x*1.7+layer*1.8)*.035+sin(x*3.1+layer)*.015+
         (dwNoise(vec2(x*5.0,layer*8.0))-.5)*.008)*height/.2*relief;
    // Broad landforms with smaller erosion folds, shared by all ground masks.
    float folds=(dwNoise(vec2(x*9.0,layer*17.1))-.5)*.009+
        (dwNoise(vec2(x*26.0,layer*5.7))-.5)*.003;
    return 1.0-height+layer*.055+
        (sin(x*2.0+layer*2.0)*.045+sin(x*5.3+layer*3.0)*.018+
         sin(x*11.0+layer)*.006+folds)*height/.2*relief;
}
vec3 dwOcean(vec3 sky,vec2 p,vec3 terrain,vec2 lightPos) {
    float horizon=1.0-terrain.y;
    if(p.y<horizon) return sky;
    float depth=clamp((p.y-horizon)/terrain.y,0.0,1.0);
    float travel=u_time*(1.0+length(u_wind)*.025);
    // Perspective increases wave spacing toward the viewer; two crossing
    // swells break the old uniformly striped plane into connected wavelets.
    float perspective=1.0/(depth+.065);
    float swell=sin(perspective*4.2-travel*1.2+p.x*3.0+
        sin(p.x*10.0-u_flow.x*14.0)*.45);
    float cross=sin(perspective*6.7-travel*.78-p.x*8.0+u_flow.y*24.0);
    float ripple=swell*.66+cross*.34;
    float detail=dwNoise(vec2(p.x*(75.0-depth*38.0),perspective*11.0-travel*.6)-u_flow*9.0);
    float fresnel=pow(1.0-depth,.75);
    vec3 reflected=dwPalette(clamp(horizon-(p.y-horizon)*1.5,0.0,1.0));
    vec3 deep=mix(vec3(.018,.05,.09),vec3(.045,.16,.19),u_daylight);
    vec3 water=mix(deep,reflected,.18+fresnel*.44);
    water*=.87+.13*ripple;
    float width=.014+depth*.16;
    float wander=sin(perspective*3.7+travel*.3)*width*.26;
    float reflection=exp(-pow((p.x-lightPos.x+wander)/width,2.0));
    float glint=smoothstep(.30,.94,ripple*.6+detail*.4);
    vec3 light=mix(vec3(.55,.67,.78),u_glowColor,u_daylight);
    water+=light*reflection*glint*(.13+u_daylight*.33)*(1.0-u_coverage*.7);
    float crests=smoothstep(.69,.92,ripple)*smoothstep(.35,.8,detail);
    water+=mix(u_color2,vec3(.50,.68,.68),u_daylight)*crests*depth*.13;
    // Near-horizon haze remains thin enough to retain a readable waterline.
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
    for(int i=0;i<5;i++) {
        // Five receding ranges suggest the long overlapping ridges of the Smokies.
        float layer=float(i)*.5;
        float ridge=dwRidge(p.x,layer,height,terrain.x);
        if(terrain.x<1.5) {
            // Woodland follows the contours in groves, with open meadow between.
            float grove=smoothstep(.30,.63,dwNoise(vec2(p.x*3.8,17.3+layer*5.0)));
            float crowns=dwNoise(vec2(p.x*(95.0+layer*46.0),7.9+layer));
            float twigs=dwNoise(vec2(p.x*380.0,layer*11.0));
            ridge-=(.003+crowns*.010+twigs*.002)*grove*(.5+layer*.28);
        }
        float fog=(.72-layer*.28)*(.65+mist*.55);
        // Slower, depth-separated ground wisps use the same wind as the clouds.
        // Their strength is art direction; it does not claim measured fog.
        if(mist>.001) {
            vec2 mistPoint=vec2(p.x*(2.8+layer),p.y*(12.0-layer*2.0));
            float wisp=dwNoise(mistPoint-u_flow*(.6+layer*.25)+layer*8.7);
            float valley=exp(-max(0.0,p.y-ridge)*38.0);
            fog+=mist*.22*(1.0-layer*.25)*smoothstep(.3,.72,wisp)*valley;
        }
        float faceX=p.x+(p.y-ridge)*.55;
        float slope=(dwRidge(faceX+.006,layer,height,terrain.x)-
            dwRidge(faceX-.006,layer,height,terrain.x))/.012;
        if(terrain.x>1.5) {
            // Spread the normal over a small face area, avoiding vertical
            // lighting stripes at the mathematical cusp of a distant peak.
            slope=(dwRidge(faceX+.025,layer,height,terrain.x)-
                dwRidge(faceX-.025,layer,height,terrain.x))/.05;
        }
        vec2 normal=normalize(vec2(-slope,-1.0));
        vec2 lightDirection=normalize(lightPos-vec2(p.x,ridge)+vec2(.001,-.001));
        float diffuse=max(0.0,dot(normal,lightDirection));
        vec3 ground=shadow*(.76+.24*diffuse)*(1.0-cloudShadow);
        vec3 pigment=mix(ground,horizon,fog);
        if(terrain.x<1.5) {
            float depth=clamp((p.y-ridge)/(.065+layer*.025),0.0,1.0);
            float fold=dwNoise(vec2(faceX*19.0+layer*11.0,p.y*9.0));
            float meadow=dwNoise(vec2(p.x*145.0,p.y*390.0)+layer*27.0);
            float thicket=dwNoise(vec2(p.x*57.0,p.y*105.0)+layer*9.0);
            vec3 green=mix(vec3(.023,.042,.058),vec3(.12,.22,.19),u_daylight);
            vec3 earth=mix(u_color0*.26,vec3(.20,.25,.19),u_daylight);
            vec3 material=mix(green,earth,smoothstep(.40,.82,fold)*.45);
            material*=.66+diffuse*.30+thicket*.17;
            material*=1.0-cloudShadow;
            float air=clamp(fog+exp(-depth*4.0)*mist*.12,0.0,.9);
            vec3 blueAir=mix(horizon,u_color2*mix(.30,.82,u_daylight),.48);
            pigment=mix(material,blueAir,air);
            // Detail diminishes into the blue atmospheric distance.
            pigment*=1.0+(meadow*.08+thicket*.06-.07)*(1.0-air);
            // Fine grass flecks emerge toward the viewer, never in the sky.
            float blades=pow(dwNoise(vec2(p.x*520.0,p.y*140.0)),5.0);
            pigment+=vec3(.035,.037,.018)*blades*depth*layer*u_daylight;
        } else if(terrain.x>1.5 && terrain.x<2.5) {
            // Altitude-shaped snowline, cut by exposed rock; mountain faces
            // inherit the same sun direction and cloud shadows as the hills.
            float altitude=1.0-height+.035+layer*.065-p.y;
            float gully=dwNoise(vec2((p.x+(p.y-ridge)*.65)*78.0,p.y*16.0)+layer*17.0);
            float rock=dwNoise(vec2(p.x*190.0,p.y*310.0)+layer*31.0);
            float snow=smoothstep(-.014,.017,altitude+(gully-.5)*.035);
            snow*=smoothstep(.14,.35,gully+altitude*3.0);
            vec3 stone=mix(vec3(.045,.060,.085),vec3(.27,.29,.30),u_daylight);
            stone*=.55+.45*diffuse+rock*.12+gully*.12;
            vec3 snowColor=mix(vec3(.19,.26,.38),vec3(.85,.90,.92),u_daylight);
            snowColor*=.68+.32*diffuse;
            vec3 mountain=mix(stone,snowColor,snow*.94)*(1.0-cloudShadow*.8);
            pigment=mix(mountain,horizon,clamp(fog,0.0,.85));
        } else if(terrain.x>2.5) {
            float depth=max(0.0,p.y-ridge);
            vec3 sand=mix(vec3(.075,.060,.058),vec3(.66,.42,.23),u_daylight);
            float face=clamp(.5+slope*3.0,0.0,1.0);
            vec3 dune=sand*(.60+diffuse*.25+face*.30)*(1.0-cloudShadow);
            pigment=mix(dune,horizon,clamp(fog*.78,0.0,.85));
            float crest=exp(-depth*230.0);
            pigment+=u_color4*crest*(.025+.075*u_daylight);
            // Wind-combed ridges wrap around dune faces; distant sand stays smooth.
            float curve=p.y*1050.0+sin(p.x*5.0)*13.0+dwNoise(vec2(p.x*7.0,p.y*23.0))*5.0;
            float ripples=sin(curve)*.5+.5;
            float grain=dwNoise(p*vec2(750.0,510.0))-.5;
            pigment*=1.0+(ripples-.5)*.065*smoothstep(.01,.12,depth)*u_daylight;
            pigment+=grain*.014*u_daylight*(1.0-fog);
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
 float ridge=1.0;
 for(int i=0;i<5;i++) ridge=min(ridge,dwRidge(p.x,float(i)*.5,terrain.y,terrain.x));
 return ridge;
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
// Tapered branches retain fine tips instead of a constant-width stick glyph.
float dwBranch(vec2 p,vec2 a,vec2 b,float root,float tip,float aa) {
    vec2 v=b-a;
    float t=clamp(dot(p-a,v)/max(dot(v,v),.000001),0.0,1.0);
    return 1.0-smoothstep(mix(root,tip,t)-aa,mix(root,tip,t)+aa,length(p-a-v*t));
}
vec3 dwTree(vec3 sky,vec2 p,float center,float base,float height,float seed,float air) {
    vec2 q=(p-vec2(center,base))/height;
    if(abs(q.x)>.95 || q.y>0.03 || q.y< -1.45) return sky;
    float aa=max(.006,1.0/(u_canvas.y*height));
    float lean=(seed-.5)*.20;
    float conifer=step(.76,seed);
    float wood=dwBranch(q,vec2(0,0),vec2(lean,-1.02),.037,.003,aa);
    float crown=0.0,shade=0.0;
    if(conifer>.5) {
        // Unequal bough tiers and a ragged edge distinguish pine from broadleaf.
        float tier=floor(clamp(-q.y,0.0,1.0)*9.0);
        float spread=(1.0+q.y)*.39;
        spread*=.75+.25*fract(-q.y*9.0+seed*3.0);
        float edge=abs(q.x-lean*(-q.y))-(spread+.014*dwNoise(q*70.0));
        crown=(1.0-smoothstep(-aa,aa,edge))*(1.0-smoothstep(-.25,-.12,q.y))*
            smoothstep(-1.08,-.97,q.y);
        shade=.4+.3*sin(tier*1.7+seed*7.0)+q.x*.4;
    } else {
        // Each branch splits into asymmetric twigs; foliage is a cluster union.
        for(int j=0;j<7;j++) {
            float k=float(j),r=dwHash(vec2(seed*87.0,k+31.0));
            float side=mod(k,2.0)*2.0-1.0;
            vec2 start=vec2(lean*(.32+k*.075),-(.32+k*.075));
            vec2 end=vec2(side*(.22+r*.22)+lean,-(.58+k*.055+r*.11));
            vec2 elbow=mix(start,end,.53)+vec2(side*.018,.035);
            wood=max(wood,dwBranch(q,start,elbow,.018-k*.0014,.010-k*.0008,aa));
            wood=max(wood,dwBranch(q,elbow,end,.010-k*.0008,.002,aa));
            vec2 tip=end+vec2(side*(.065+r*.065),-.12-r*.10);
            wood=max(wood,dwBranch(q,mix(elbow,end,.65),tip,.006,.001,aa));
            vec2 fork=end+vec2(-side*.07,-.12);
            wood=max(wood,dwBranch(q,mix(elbow,end,.8),fork,.005,.001,aa));
            vec2 leafCenter=end+vec2(-side*.025,-.04);
            vec2 shape=(q-leafCenter)/vec2(.19+r*.08,.17+r*.07);
            float edge=length(shape)-1.0;
            edge+=(dwNoise(q*38.0+seed*71.0)-.5)*.23;
            float cluster=1.0-smoothstep(-aa*3.0,aa*3.0,edge);
            if(cluster>crown) shade=r*.55+q.x*.3-q.y*.16;
            crown=max(crown,cluster);
        }
        vec2 leader=(q-vec2(lean,-1.02))/vec2(.21+seed*.05,.23);
        float leaderEdge=length(leader)-1.0+(dwNoise(q*38.0+seed*71.0)-.5)*.23;
        float leaderCrown=1.0-smoothstep(-aa*3.0,aa*3.0,leaderEdge);
        if(leaderCrown>crown) shade=.42;
        crown=max(crown,leaderCrown);
        float foliage=clamp(u_season.y*.90+u_season.z+u_season.w*.73,0.0,1.0);
        // Autumn opens small gaps between leaf masses; winter exposes twigs.
        float gaps=smoothstep(.12,.34,dwNoise(q*31.0+seed*41.0)+foliage*.25);
        crown*=foliage*gaps;
    }
    vec3 haze=u_color4*mix(.30,.83,u_daylight);
    vec3 bark=mix(vec3(.020,.026,.037),vec3(.15,.12,.085),u_daylight);
    bark*=1.0-u_surface.y*.2;
    sky=mix(sky,mix(bark,haze,air),wood);
    vec3 leafColor=vec3(.18,.31,.17)*u_season.y+vec3(.10,.23,.15)*u_season.z+
        mix(vec3(.34,.17,.055),vec3(.52,.32,.10),seed)*u_season.w;
    if(conifer>.5) leafColor=vec3(.09,.19,.16);
    float leafDetail=dwNoise(q*23.0+seed*31.0)*.7+dwNoise(q*71.0)*.3;
    leafColor*=mix(.19,1.0,u_daylight)*(.58+shade*.32+leafDetail*.34);
    leafColor*=1.0-u_surface.y*.18;
    // Snow catches exposed crown edges and pine boughs, retaining dark pockets.
    float snow=u_surface.x*smoothstep(.45,.75,dwNoise(q*25.0)+shade*.3);
    leafColor=mix(leafColor,mix(vec3(.16,.21,.30),vec3(.80,.86,.88),u_daylight),snow*.85);
    return mix(sky,mix(leafColor,haze,air),crown);
}
vec3 dwLivingSeason(vec3 sky,vec2 p,vec3 terrain) {
    if(terrain.x<.5||terrain.x>2.5) return sky;
    float ridge=dwLivingRidge(p,terrain),ground=smoothstep(ridge,ridge+.008,p.y);
    vec3 tint=vec3(1.0)+u_season.x*vec3(-.07,-.02,.08)+
        u_season.y*vec3(-.03,.07,-.02)+u_season.w*vec3(.13,-.01,-.10);
    sky=mix(sky,sky*tint,ground*.65*(1.0-u_surface.x));
    for(int row=0;row<2;row++) {
        float layer=float(row),frequency=mix(16.0,8.5,layer);
        float cell=floor(p.x*frequency);
        // Adjacent cells are evaluated so crowns never clip at a cell boundary.
        for(int n=-1;n<=1;n++) {
            float id=cell+float(n),seed=dwHash(vec2(id,71.3+layer*29.0));
            float center=(id+.18+seed*.64)/frequency;
            float grove=dwNoise(vec2(center*3.1,15.7+layer));
            if(seed<.15 || grove<.33) continue;
            float base=dwRidge(center,layer+1.0,terrain.y,terrain.x)+.014;
            float height=(.030+pow(seed,.65)*.056)*mix(.72,1.1,layer);
            float air=(.22-layer*.15)*(.6+terrain.z*.8);
            sky=dwTree(sky,p,center,base,height,seed,air);
        }
    }
    return sky;
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
