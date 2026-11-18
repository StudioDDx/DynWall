// Independent transparent valley-fog pass for painted landscape depth layers.
// Coordinates are full virtual-desktop UV, so monitor boundaries never reset the noise.
uniform vec2 u_canvas;
uniform vec4 u_view;
uniform float u_time;
uniform vec2 u_flow;
uniform float u_daylight;
uniform float u_coverage;
uniform float u_rain;
uniform float u_mist;
uniform float u_band;
float fogHash(vec2 p) {
    p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);
    return fract(p.x*p.y);
}
float fogNoise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
    return mix(mix(fogHash(i),fogHash(i+vec2(1,0)),f.x),
               mix(fogHash(i+vec2(0,1)),fogHash(i+vec2(1,1)),f.x),f.y);
}
float fogFbm(vec2 p) {
    float n=0.0,a=.55;
    for(int i=0;i<4;i++){n+=a*fogNoise(p);p=p*2.07+vec2(7.1,13.3);a*=.48;}
    return n;
}
vec4 dynwallFog(vec2 uv) {
    // u_band: 0 is distant haze; 1 is the lower valley; 2 is near-treeline mist.
    vec2 p=vec2((u_view.x+uv.x*u_view.z)/u_canvas.x,
                (u_view.y+uv.y*u_view.w)/u_canvas.y);
    float nearBand=step(1.5,u_band),lower=step(.5,u_band);
    float center=mix(.49,.60,lower)+nearBand*.105;
    float spread=mix(.088,.072,lower)+nearBand*.018;
    float envelope=exp(-pow((p.y-center)/spread,2.0));
    // Separate noise scales produce soft mass and slowly changing filaments.
    vec2 flow=u_flow*mix(.19,.40,lower);
    vec2 q=vec2(p.x*4.7,p.y*19.0)-flow+vec2(u_time*.0017,u_time*.00024);
    float cloud=fogFbm(q+vec2(u_band*21.6,u_band*3.2));
    float detail=fogFbm(q*2.05-vec2(u_time*.0007,0.0));
    float density=smoothstep(.30,.74,cloud*.72+detail*.28);
    float weather=clamp(.35+u_coverage*.42+u_rain*.45,0.20,1.0);
    float alpha=clamp(envelope*density*weather*u_mist*mix(.34,.47,lower),0.0,.48);
    vec3 tint=mix(vec3(.34,.45,.52),vec3(.64,.74,.74),u_daylight);
    // Premultiplied output for the normal GNOME background actor blend path.
    return vec4(tint*alpha,alpha);
}
