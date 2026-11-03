#!/usr/bin/env python3
"""Compile and render the exact production GLSL into isolated EGL pbuffers.

No GNOME compositor hooks, extension enablement, or wallpaper mutation.
Requires system EGL/OpenGL, Python Pillow, and Node. Outputs PNG + measurements.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import time
import statistics
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]

def run(output, width, height, device=None, quality='balanced', reference_dir=None, timing_runs=5, shader_path=None, living_enabled=True):
    assert timing_runs >= 3, 'Use at least three timing samples for a median'
    shader_source = Path(shader_path) if shader_path else ROOT / 'extension/weather.glsl'
    shader = shader_source.read_text()
    egl = C.CDLL('libEGL.so.1')
    gl = C.CDLL('libGL.so.1')
    def bind(lib, name, result, args):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
        return fn
    ptr, integer, uint, flt = C.c_void_p, C.c_int, C.c_uint, C.c_float
    get_display = bind(egl,'eglGetDisplay',ptr,[ptr])
    initialize = bind(egl,'eglInitialize',uint,[ptr,C.POINTER(integer),C.POINTER(integer)])
    choose = bind(egl,'eglChooseConfig',uint,[ptr,C.POINTER(integer),C.POINTER(ptr),integer,C.POINTER(integer)])
    bind_api = bind(egl,'eglBindAPI',uint,[uint])
    surface_fn = bind(egl,'eglCreatePbufferSurface',ptr,[ptr,ptr,C.POINTER(integer)])
    context_fn = bind(egl,'eglCreateContext',ptr,[ptr,ptr,ptr,C.POINTER(integer)])
    current = bind(egl,'eglMakeCurrent',uint,[ptr,ptr,ptr,ptr])
    display = get_display(None)
    if device is not None:
        proc = bind(egl, 'eglGetProcAddress', ptr, [C.c_char_p])
        query = C.CFUNCTYPE(uint, integer, C.POINTER(ptr), C.POINTER(integer))(proc(b'eglQueryDevicesEXT'))
        platform = C.CFUNCTYPE(ptr, uint, ptr, ptr)(proc(b'eglGetPlatformDisplayEXT'))
        devices, count = (ptr * 16)(), integer()
        assert query(16, devices, C.byref(count)) and 0 <= device < count.value, 'EGL device unavailable'
        display = platform(0x313F, devices[device], None)
    major, minor = integer(), integer()
    assert initialize(display,C.byref(major),C.byref(minor)), 'EGL initialization failed'
    attrs = (integer * 13)(0x3033,1,0x3040,8,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038)
    config,count=ptr(),integer()
    assert choose(display,attrs,C.byref(config),1,C.byref(count)) and count.value, 'No OpenGL pbuffer config'
    assert bind_api(0x30A2)
    surf=surface_fn(display,config,(integer*5)(0x3057,width,0x3056,height,0x3038))
    context=context_fn(display,config,None,(integer*5)(0x3098,3,0x30FB,3,0x3038))
    assert surf and context and current(display,surf,surf,context), 'OpenGL context creation failed'
    get_string=bind(gl,'glGetString',C.c_char_p,[uint])
    renderer=get_string(0x1F01).decode()
    print('GPU:',renderer,'GL:',get_string(0x1F02).decode())
    create=bind(gl,'glCreateShader',uint,[uint]); source=bind(gl,'glShaderSource',None,[uint,integer,C.POINTER(C.c_char_p),ptr])
    compile_fn=bind(gl,'glCompileShader',None,[uint]); getiv=bind(gl,'glGetShaderiv',None,[uint,uint,C.POINTER(integer)])
    getlog=bind(gl,'glGetShaderInfoLog',None,[uint,integer,ptr,C.c_char_p])
    def compile_shader(kind,text):
        obj=create(kind); encoded=C.c_char_p(text.encode()); source(obj,1,C.byref(encoded),None); compile_fn(obj)
        ok=integer(); getiv(obj,0x8B81,C.byref(ok))
        log=C.create_string_buffer(65536); getlog(obj,len(log),None,log)
        assert ok.value,log.value.decode()
        return obj
    vertex=compile_shader(0x8B31,'#version 330\nout vec2 v_uv;\nvoid main(){ vec2 p=vec2((gl_VertexID << 1) & 2,gl_VertexID & 2);v_uv=p;gl_Position=vec4(p*2.0-1.0,0,1);}')
    fragment=compile_shader(0x8B30,'#version 330\nin vec2 v_uv;out vec4 outColor;\n'+shader+'\nvoid main(){outColor=vec4(dynwall(vec2(v_uv.x,1.0-v_uv.y)),1.0);}')
    program=bind(gl,'glCreateProgram',uint,[])()
    attach=bind(gl,'glAttachShader',None,[uint,uint]);attach(program,vertex);attach(program,fragment)
    bind(gl,'glLinkProgram',None,[uint])(program)
    ok=integer();bind(gl,'glGetProgramiv',None,[uint,uint,C.POINTER(integer)])(program,0x8B82,C.byref(ok))
    assert ok.value,'Program link failed'
    bind(gl,'glUseProgram',None,[uint])(program)
    vao=uint();bind(gl,'glGenVertexArrays',None,[integer,C.POINTER(uint)])(1,C.byref(vao));bind(gl,'glBindVertexArray',None,[uint])(vao)
    uniform_location=bind(gl,'glGetUniformLocation',integer,[uint,C.c_char_p])
    def uniform(name,value):
        value=value if isinstance(value,list) else [value]
        location=uniform_location(program,name.encode())
        if location>=0:
            bind(gl,f'glUniform{len(value)}fv',None,[integer,integer,C.POINTER(flt)])(location,1,(flt*len(value))(*value))
    bind(gl,'glViewport',None,[integer,integer,integer,integer])(0,0,width,height)
    draw=bind(gl,'glDrawArrays',None,[uint,integer,integer]);finish=bind(gl,'glFinish',None,[])
    read=bind(gl,'glReadPixels',None,[integer,integer,integer,integer,uint,uint,ptr])
    def render():
        draw(4,0,3);finish()
        data=(C.c_ubyte*(width*height*4))();read(0,0,width,height,0x1908,0x1401,data)
        return Image.frombytes('RGBA',(width,height),bytes(data)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB')
    fixtures=json.loads(subprocess.check_output(['node',str(ROOT/'tests/renderer-fixtures.mjs')],text=True))
    for fixture in fixtures:
        fixture['uniforms']['u_quality'] = {'low': 0, 'balanced': 1, 'high': 2}[quality]
    output.mkdir(parents=True,exist_ok=True)
    reference_dir = Path(reference_dir) if reference_dir else None
    def capture(name, image, reference_required=True):
        image.save(output / f'{name}.png')
        if reference_dir:
            expected_path = reference_dir / f'{name}.png'
            if not expected_path.exists() and not reference_required:
                return
            assert expected_path.exists(), f'Missing reference image: {expected_path}'
            expected = Image.open(expected_path).convert('RGB')
            assert image.size == expected.size, f'Reference size differs for {name}'
            assert ImageChops.difference(image, expected).getbbox() is None, f'Render changed for {name}'
    images={}; timings={}
    for fixture in fixtures:
        for name,value in fixture['uniforms'].items():uniform(name,value)
        uniform('u_canvas',[width,height]);uniform('u_view',[0,0,width,height])
        frame=render();capture(fixture['name'], frame);images[fixture['name']]=frame
        samples=[]
        for _ in range(timing_runs):
            start=time.perf_counter()
            for i in range(10):uniform('u_time',12+i/30);draw(4,0,3);finish()
            samples.append(round((time.perf_counter()-start)*100,2))
        timings[fixture['name']]=samples
        assert max(ImageStat.Stat(frame).stddev)>2,'Renderer produced a flat image'
    # Depth is confined below the skyline; static terrain must not drift with time.
    for name, value in fixtures[0]['uniforms'].items(): uniform(name, value)
    for name in ['u_grain', 'u_stars', 'u_coverage', 'u_rain', 'u_snow', 'u_celestialDrift', 'u_glowPulse']:
        uniform(name, 0)
    uniform('u_landscape', [0, .2, .5]); sky_only = render(); capture('sky-only', sky_only)
    uniform('u_landscape', [1, .2, .5]); landscape = render(); capture('landscape-depth', landscape)
    depth_delta = ImageChops.difference(sky_only, landscape)
    assert depth_delta.crop((0, 0, width, int(height*.65))).getbbox() is None, 'Landscape obscures the upper sky'
    landscape_signal = sum(ImageStat.Stat(depth_delta.crop((0, int(height*.85), width, height))).mean) / 3
    assert landscape_signal > 2, f'Landscape has no visible depth: {landscape_signal}'
    # The palette reaches its horizon color at the visible horizon rather than
    # continuing through terrain hidden below it.
    for name, value in {
        'u_color0': [0, 0, 0], 'u_color1': [1, 1, 1], 'u_color2': [1, 1, 1],
        'u_color3': [1, 1, 1], 'u_color4': [1, 1, 1],
        'u_positions': [0, 1, 1, 1], 'u_position4': 1, 'u_stopCount': 2,
        'u_glow': [0, 0, 0, 0], 'u_celestial': [0, 0, .03, 0],
        'u_mesh': [0, 18, 0], 'u_vignette': 0, 'u_grain': 0,
        'u_coverage': 0, 'u_rain': 0, 'u_snow': 0, 'u_daylight': 1,
        'u_custom': [0, 0, 0, 0], 'u_landscape': [0, .2, 0],
    }.items(): uniform(name, value)
    proportioned_sky = render()
    horizon_pixel = proportioned_sky.getpixel((width // 2, int(height * .79)))
    assert min(horizon_pixel) > 245, f'Sky gradient does not reach the horizon: {horizon_pixel}'

    # Terrain scale changes relief, not the selected horizon. Ocean has no
    # relief, making any horizon drift directly observable.
    uniform('u_landscape', [0, .2, 0]); uniform('u_custom', [0, 0, 0, 0]); ocean_sky = render()
    uniform('u_landscape', [4, .2, 0]); ocean_default = render()
    default_top = ImageChops.difference(ocean_sky, ocean_default).getbbox()[1]
    uniform('u_landscape', [0, .2, 0]); uniform('u_custom', [0, .75, 0, 0]); scaled_sky = render()
    uniform('u_landscape', [4, .2, 0]); ocean_scaled = render()
    scaled_top = ImageChops.difference(scaled_sky, ocean_scaled).getbbox()[1]
    assert abs(default_top-scaled_top) <= 1, f'Terrain scale moved the horizon: {default_top} -> {scaled_top}'
    for name, value in fixtures[0]['uniforms'].items(): uniform(name, value)
    for name in ['u_grain', 'u_stars', 'u_coverage', 'u_rain', 'u_snow', 'u_celestialDrift', 'u_glowPulse']:
        uniform(name, 0)
    uniform('u_custom', [0, 0, 0, 0])
    uniform('u_landscape', [0, .2, .5]); sky_only = render()
    uniform('u_landscape', [1, .2, .5]); landscape = render()
    # Each background must change the actual terrain, independently of palette.
    # Calm water remains still; reported wind advects only its surface details.
    style_signals = {}
    previous = landscape
    for style in [2, 3, 4]:
        uniform('u_landscape', [style, .2, .5])
        uniform('u_flow', [0, 0]); uniform('u_time', 12)
        still = render()
        delta = ImageChops.difference(sky_only, still)
        assert delta.crop((0, 0, width, int(height*.6))).getbbox() is None, 'New terrain obscures the upper sky'
        signal = sum(ImageStat.Stat(ImageChops.difference(previous, still)).mean)/3
        assert signal > .4, f'Background style {style} is not visibly distinct: {signal}'
        style_signals[style] = signal
        uniform('u_time', 1200)
        later = render()
        if style == 4:
            assert ImageChops.difference(still, later).getbbox(), 'Ocean swell freezes without wind'
        else:
            assert ImageChops.difference(still, later).getbbox() is None, f'Calm background {style} drifts'
        if style == 4:
            uniform('u_flow', [.2, .015])
            moving_water = render()
            water_delta = ImageChops.difference(still, moving_water)
            assert water_delta.getbbox() and water_delta.getbbox()[1] >= int(height*.79), 'Wind does not move water locally'
        previous = still
    uniform('u_flow', fixtures[0]['uniforms']['u_flow'])
    uniform('u_time', 12)
    uniform('u_landscape', [1, .2, .5])
    # Already-loaded GNOME modules may not upload the newly introduced uniform.
    uniform('u_landscape', [0, 0, 0])
    assert ImageChops.difference(landscape, render()).getbbox() is None, 'Older controllers lose default landscape depth'
    uniform('u_landscape', [1, .2, .5])
    uniform('u_time', 1200)
    assert ImageChops.difference(landscape, render()).getbbox() is None, 'Terrain slides with animation time'
    # Preserve the light position when hiding the disc: slope lighting is allowed
    # to change with the light direction, but the disc must remain occluded.
    uniform('u_glow', [.73, .985, 0, 0])
    uniform('u_time', 12); uniform('u_celestial', [.73, .985, .03, 1]); behind_terrain = render()
    uniform('u_celestial', [.73, .985, .03, 0]); no_disc = render()
    assert ImageChops.difference(behind_terrain, no_disc).crop((0, int(height*.98), width, height)).getbbox() is None, 'Celestial disc paints over foreground terrain'
    # Isolate cloud advection from film grain, stars, celestial drift and glow pulse.
    for name,value in fixtures[0]['uniforms'].items():uniform(name,value)
    for name in ['u_grain', 'u_stars', 'u_celestialDrift', 'u_glowPulse', 'u_rain', 'u_snow']: uniform(name, 0)
    uniform('u_landscape', [1, .2, 0])
    first=render();capture('zero-control-first', first)
    uniform('u_time',27)
    assert ImageChops.difference(first, render()).getbbox() is None, 'Cloud field drifts independently of integrated wind'
    uniform('u_flow',[.12,.012]);second=render();capture('zero-control-second', second)
    motion=sum(ImageStat.Stat(ImageChops.difference(first,second)).mean)/3
    assert motion>0.2,f'No meaningful motion: {motion}'
    foreground = (0, int(height*.96), width, height)
    shadow_motion = sum(ImageStat.Stat(ImageChops.difference(first, second).crop(foreground)).mean) / 3
    assert shadow_motion > .05, f'Wind-driven clouds cast no moving terrain shadows: {shadow_motion}'
    uniform('u_landscape', [0, .2, .5])
    uniform('u_coverage', 0); uniform('u_time', 12); uniform('u_flow', [.02, .002]); clear_first=render()
    uniform('u_time', 27); uniform('u_flow', [.12, .012]); clear_second=render()
    assert max(ImageChops.difference(clear_first, clear_second).getextrema()[0]) == 0, 'Cloud motion control still has another animated layer'
    # Art-directed mist drifts with wind at ground level; hills stay anchored.
    uniform('u_landscape', [1, .2, 0]); uniform('u_flow', [0, 0]); bare_first=render()
    uniform('u_flow', [.3, .03]); bare_second=render()
    assert ImageChops.difference(bare_first, bare_second).getbbox() is None, 'Bare terrain drifts with wind'
    uniform('u_landscape', [1, .2, .8]); uniform('u_flow', [0, 0]); mist_first=render()
    uniform('u_flow', [.3, .03]); mist_second=render()
    mist_motion = sum(ImageStat.Stat(ImageChops.difference(mist_first, mist_second).crop(foreground)).mean) / 3
    assert mist_motion > .015, f'No wind-driven mist: {mist_motion}'
    assert ImageChops.difference(mist_first, mist_second).crop((0, 0, width, int(height*.65))).getbbox() is None, 'Ground mist obscures the upper sky'
    # Isolate rain completely: two frames of a black sky, with only drops moving.
    # For fixed q cells, vertical displacement is dt * (speed / scale) * height.
    # Reported west wind (+x) must carry falling drops right, not left.
    for name, value in fixtures[0]['uniforms'].items(): uniform(name, value)
    for name in ['u_color0', 'u_color1', 'u_color2', 'u_color3', 'u_color4']:
        uniform(name, [0, 0, 0])
    for name in ['u_coverage', 'u_snow', 'u_stars', 'u_grain', 'u_vignette']:
        uniform(name, 0)
    uniform('u_glow', [.5, .5, .5, 0]); uniform('u_celestial', [.5, .5, .04, 0])
    uniform('u_mesh', [0, 18, .08]); uniform('u_rain', 1); uniform('u_daylight', 1)
    uniform('u_landscape', [0, .2, .5])
    rain_direction_error = {}
    dt = .06
    dy = round(dt * 31 / 56 * height)
    dx = round(.55 * dy)
    for wind in [5, -5]:
        uniform('u_wind', [wind, 0]); uniform('u_time', 12)
        first_rain = render()
        uniform('u_time', 12 + dt); second_rain = render()
        source = first_rain.crop((dx, 0, width-dx, height-dy))
        errors = {}
        for direction in [1, -1]:
            shifted = second_rain.crop((dx+direction*dx, dy, width-dx+direction*dx, height))
            errors[direction] = sum(ImageStat.Stat(ImageChops.difference(source, shifted)).mean)
        expected = 1 if wind > 0 else -1
        rain_direction_error[wind] = {'with_wind': errors[expected], 'against_wind': errors[-expected]}
        assert errors[expected] < errors[-expected] * .8, f'Rain drifts against wind: {rain_direction_error}'
    # Turning off only rain must remove the visible drops (no cloud/wind confound).
    uniform('u_rain', 0)
    no_rain = render()
    assert max(no_rain.getextrema()[0]) == 0, 'Isolated rain control is not black'
    assert sum(ImageStat.Stat(ImageChops.difference(second_rain, no_rain)).mean) > .1, 'Rain has no rendered effect'
    # Wind is integrated by the controller. A new wind observation must not
    # teleport the snow pattern at the same animation time and flow offset.
    uniform('u_snow', .8); uniform('u_wind', [20, 0]); uniform('u_flow', [0, 0]); snow_first=render()
    uniform('u_wind', [-20, 0]); snow_changed_wind=render()
    assert ImageChops.difference(snow_first, snow_changed_wind).getbbox() is None, 'Wind observations teleport snow'
    uniform('u_flow', [.08, 0]); snow_advected=render()
    snow_motion = sum(ImageStat.Stat(ImageChops.difference(snow_first, snow_advected)).mean) / 3
    assert snow_motion > .02, f'Integrated wind does not advect snow: {snow_motion}'
    # Cloud opacity must suppress the same star field, not merely change background color.
    star_signal = {}
    for cover in [0, 1]:
        for name, value in fixtures[5]['uniforms'].items(): uniform(name, value)
        uniform('u_coverage', cover)
        with_stars = render(); uniform('u_stars', 0); without_stars = render()
        star_signal[cover] = sum(ImageStat.Stat(ImageChops.difference(with_stars, without_stars)).mean)
    assert star_signal[0] > .005, 'Star field is not rendered'
    assert star_signal[1] < star_signal[0] * .25, f'Clouds do not occlude stars: {star_signal}'
    # Turbulence changes stellar intensity, while the star positions stay fixed.
    for name, value in fixtures[5]['uniforms'].items(): uniform(name, value)
    for name in ['u_grain', 'u_glowPulse', 'u_celestialDrift', 'u_rain', 'u_snow']: uniform(name, 0)
    uniform('u_landscape', [0, .2, .5]); uniform('u_wind', [0, 0]); calm_stars=render()
    uniform('u_wind', [15, 0]); windy_stars=render()
    scintillation = sum(ImageStat.Stat(ImageChops.difference(calm_stars, windy_stars)).mean) / 3
    assert scintillation > .001, f'Star scintillation ignores wind turbulence: {scintillation}'
    uniform('u_time', 14); later_stars=render()
    twinkle = sum(ImageStat.Stat(ImageChops.difference(windy_stars, later_stars)).mean) / 3
    assert twinkle > .001, f'No time-varying stellar twinkle: {twinkle}'
    # Autumn leaves are decorative: zero strength must be exactly transparent.
    for name, value in fixtures[0]['uniforms'].items(): uniform(name, value)
    for name in ['u_coverage', 'u_rain', 'u_snow', 'u_grain', 'u_stars', 'u_celestialDrift', 'u_glowPulse']:
        uniform(name, 0)
    still_sky = render()
    uniform('u_leaves', [4, 0, 1, 7]); quiet_leaves = render()
    assert ImageChops.difference(still_sky, quiet_leaves).getbbox() is None, 'Quiet gust changes the sky'
    uniform('u_leaves', [.5, 1, 1, 7]); entering_leaves = ImageChops.difference(still_sky, render())
    entry_left = sum(ImageStat.Stat(entering_leaves.crop((0, 0, width // 4, height))).mean) / 3
    entry_right = sum(ImageStat.Stat(entering_leaves.crop((width * 3 // 4, 0, width, height))).mean) / 3
    assert entry_left > .01 and entry_right < entry_left * .05, \
        f'Leaves materialize away from the upwind edge: left={entry_left}, right={entry_right}'
    uniform('u_leaves', [4, 1, 1, 7]); leaves_first = render(); capture('autumn-gust', leaves_first)
    leaf_signal = sum(ImageStat.Stat(ImageChops.difference(still_sky, leaves_first)).mean) / 3
    assert leaf_signal > .05, f'Leaves are not visible: {leaf_signal}'
    uniform('u_landscape', [4, .2, .5]); uniform('u_leaves', [4, 0, 1, 7])
    ocean_without_leaves = render()
    uniform('u_leaves', [4, 1, 1, 7])
    assert ImageChops.difference(ocean_without_leaves, render()).getbbox() is None, 'Leaves appear over open ocean'
    uniform('u_landscape', fixtures[0]['uniforms']['u_landscape'])
    gust_timings = []
    for _ in range(timing_runs):
        start = time.perf_counter()
        for index in range(10):
            uniform('u_leaves', [4 + index / 30, 1, 1, 7]); draw(4, 0, 3); finish()
        gust_timings.append(round((time.perf_counter() - start) * 100, 2))
    uniform('u_leaves', [5, 1, 1, 7]); leaves_second = render()
    assert sum(ImageStat.Stat(ImageChops.difference(leaves_first, leaves_second)).mean) / 3 > .05, 'Leaves do not tumble or drift'
    # Use the isolated leaf signal to verify travel in both horizontal directions.
    leaf_direction_error = {}
    dt = .06
    dx, dy = max(1, round(.22 * dt * height)), max(1, round(.07 * dt * height))
    for direction in [1, -1]:
        uniform('u_leaves', [4, 1, direction, 7]); first = ImageChops.difference(render(), still_sky)
        uniform('u_leaves', [4 + dt, 1, direction, 7]); second = ImageChops.difference(render(), still_sky)
        source = first.crop((dx, 0, width-dx, height-dy))
        errors = {}
        for sign in [1, -1]:
            shifted = second.crop((dx+sign*dx, dy, width-dx+sign*dx, height))
            errors[sign] = sum(ImageStat.Stat(ImageChops.difference(source, shifted)).mean)
        leaf_direction_error[direction] = {'with_wind': errors[direction], 'against_wind': errors[-direction]}
        assert errors[direction] < errors[-direction] * .85, f'Leaves drift against gust: {leaf_direction_error}'
    frames = []
    for index in range(30):
        uniform('u_leaves', [2 + index / 10, 1, 1, 7])
        frames.append(render())
    frames[0].save(output / 'autumn-gust.gif', save_all=True, append_images=frames[1:], duration=100, loop=0)
    # Partitioning a continuous virtual canvas into monitors must not move the sky.
    for name, value in fixtures[0]['uniforms'].items(): uniform(name, value)
    reference = render()
    half = width // 2
    seam_deltas = []
    for offset, size in [(0, half), (half, width - half)]:
        bind(gl, 'glViewport', None, [integer, integer, integer, integer])(0, 0, size, height)
        uniform('u_view', [offset, 0, size, height])
        partition = render().crop((0, 0, size, height)); capture(f'seam-{offset}', partition)
        expected = reference.crop((offset, 0, offset + size, height))
        delta = sum(ImageStat.Stat(ImageChops.difference(partition, expected)).mean) / 3
        seam_deltas.append(delta)
        assert delta < .12, f'Monitor coordinates are discontinuous: {delta}'
    bind(gl, 'glViewport', None, [integer, integer, integer, integer])(0, 0, width, height)
    uniform('u_view', [0, 0, width, height])
    # Repeat with an active gust: particles must not jump at a monitor seam.
    uniform('u_leaves', [4, 1, 1, 7]); reference = render()
    for offset, size in [(0, half), (half, width-half)]:
        bind(gl, 'glViewport', None, [integer, integer, integer, integer])(0, 0, size, height)
        uniform('u_view', [offset, 0, size, height])
        partition = render().crop((0, 0, size, height))
        delta = sum(ImageStat.Stat(ImageChops.difference(partition, reference.crop((offset, 0, offset+size, height)))).mean) / 3
        assert delta < .12, f'Autumn leaves jump at monitor seam: {delta}'
    bind(gl, 'glViewport', None, [integer, integer, integer, integer])(0, 0, width, height)
    uniform('u_view', [0, 0, width, height])
    # Additional fixtures exercise the exact same production shader after the
    # legacy regression assertions. Reset every added uniform between captures.
    living_signals = {}
    neutral = {'u_custom': [0,0,0,0], 'u_tint': [0,0], 'u_surface': [0,0],
               'u_season': [0,0,0,0], 'u_moments': [0,0,0,0], 'u_birds': [0,0,0]}
    living_path = ROOT/'tests/living-fixtures.mjs'
    if living_enabled and living_path.exists():
        living = json.loads(subprocess.check_output(['node', str(living_path)], text=True))
        living += json.loads(subprocess.check_output(['node', str(ROOT/'tests/living-preview-fixtures.mjs')], text=True))
        for fixture in living:
            for name,value in {**fixtures[0]['uniforms'], **neutral, 'u_leaves':[0,0,0,0], **fixture['uniforms']}.items(): uniform(name,value)
            uniform('u_canvas',[width,height]);uniform('u_view',[0,0,width,height])
            frame=render();capture(fixture['name'],frame,False);images[fixture['name']]=frame
            if fixture.get('reference'):
                reference=images[fixture['reference']]
                signal=sum(ImageStat.Stat(ImageChops.difference(frame,reference)).mean)/3
                living_signals[fixture['name']]=signal
                assert signal > fixture.get('minimum_signal', .0001), f"Living effect invisible: {fixture['name']} {signal}"
            samples=[]
            for _ in range(timing_runs):
                start=time.perf_counter()
                for index in range(10): draw(4,0,3);finish()
                samples.append(round((time.perf_counter()-start)*100,2))
            timings[fixture['name']]=samples
        # A real local cutout over an actual production-rendered animated sky.
        import sys
        sys.path.insert(0,str(ROOT))
        from dynwall_living import load_pack, pack_directory, composite_pack
        for name,value in {**fixtures[0]['uniforms'],**neutral,'u_leaves':[0,0,0,0],'u_landscape':[0,.2,.5]}.items():uniform(name,value)
        sky=render();capture('pack-sky-production',sky,False)
        packed=composite_pack(sky,load_pack(pack_directory('woodland')), {})
        capture('pack-woodland-production',packed,False)
        difference=ImageChops.difference(sky,packed)
        assert difference.crop((0,0,width,int(height*.4))).getbbox() is None, 'Pack covers upper animated sky'
        signal=sum(ImageStat.Stat(difference).mean)/3
        assert signal>1, 'Pack foreground is invisible'
        living_signals['pack-woodland-production']=signal
    measurements={'renderer':renderer,'quality':quality,'width':width,'height':height,
        'frame_timing_samples_ms':timings,
        'median_frame_ms':{name:statistics.median(samples) for name,samples in timings.items()},
        'motion_pixel_delta':motion,'star_signal_clear_overcast':star_signal,
        'rain_direction_error':rain_direction_error,'monitor_partition_pixel_delta':seam_deltas,
        'leaf_signal':leaf_signal,'leaf_direction_error':leaf_direction_error,
        'isolated_gust_frame_samples_ms':gust_timings,
        'isolated_gust_median_frame_ms':statistics.median(gust_timings),
        'production_shader':str(shader_source)}
    measurements['living_effect_signal'] = living_signals
    measurements['landscape_signal'] = landscape_signal
    measurements['background_style_signal'] = style_signals
    measurements['terrain_shadow_motion'] = shadow_motion
    measurements['mist_motion'] = mist_motion
    measurements['snow_advection'] = snow_motion
    measurements['wind_scintillation'] = scintillation
    measurements['star_twinkle'] = twinkle
    (output/'measurements.json').write_text(json.dumps(measurements,indent=2)+'\n')
    print(json.dumps(measurements,indent=2))
    # Explicitly release all native objects, including on normal harness completion.
    bind(gl,'glDeleteProgram',None,[uint])(program)
    for obj in [vertex,fragment]:bind(gl,'glDeleteShader',None,[uint])(obj)
    bind(gl,'glDeleteVertexArrays',None,[integer,C.POINTER(uint)])(1,C.byref(vao))
    current(display,None,None,None)
    bind(egl,'eglDestroyContext',uint,[ptr,ptr])(display,context)
    bind(egl,'eglDestroySurface',uint,[ptr,ptr])(display,surf)
    bind(egl,'eglTerminate',uint,[ptr])(display)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('/tmp/dynwall-shader-preview'));parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=720);parser.add_argument('--device',type=int,default=None,help='EGL device index (0 is NVIDIA on the target desktop)')
    parser.add_argument('--quality',choices=['low','balanced','high'],default='balanced')
    parser.add_argument('--reference-dir',type=Path,help='Require byte-exact RGB matches to baseline PNGs')
    parser.add_argument('--timing-runs',type=int,default=5,help='Repeated 10-frame samples; median is recorded')
    parser.add_argument('--shader', type=Path, help='Explicit baseline shader source; default is exact production source')
    parser.add_argument('--baseline-only', action='store_true', help='Run legacy regression fixtures without newly added effects')
    args=parser.parse_args();run(args.output,args.width,args.height,args.device,args.quality,args.reference_dir,args.timing_runs,args.shader,not args.baseline_only)
