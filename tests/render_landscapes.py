#!/usr/bin/env python3
"""Fast landscape previews and continuity checks using the production GLSL.

Uses isolated EGL pbuffers; never enables an extension or changes a wallpaper.
Run a baseline with --shader, then compare unchanged sky with --reference-dir.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
NEUTRAL = {
    'u_custom': [0, 0, 0, 0], 'u_tint': [0, 0], 'u_surface': [0, 0],
    'u_season': [0, 0, 0, 0], 'u_moments': [0, 0, 0, 0], 'u_birds': [0, 0, 0],
    'u_leaves': [0, 0, 0, 0],
}


class Renderer:
    def __init__(self, width, height, shader, device=None):
        self.width, self.height = width, height
        self.egl, self.gl = C.CDLL('libEGL.so.1'), C.CDLL('libGL.so.1')
        self.display = self.bind(self.egl, 'eglGetDisplay', C.c_void_p, [C.c_void_p])(None)
        if device is not None:
            proc = self.bind(self.egl, 'eglGetProcAddress', C.c_void_p, [C.c_char_p])
            query = C.CFUNCTYPE(C.c_uint, C.c_int, C.POINTER(C.c_void_p), C.POINTER(C.c_int))(proc(b'eglQueryDevicesEXT'))
            platform = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p)(proc(b'eglGetPlatformDisplayEXT'))
            devices, count = (C.c_void_p * 16)(), C.c_int()
            assert query(16, devices, C.byref(count)) and 0 <= device < count.value, 'EGL device unavailable'
            self.display = platform(0x313F, devices[device], None)
        major, minor = C.c_int(), C.c_int()
        assert self.bind(self.egl, 'eglInitialize', C.c_uint, [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)])(self.display, C.byref(major), C.byref(minor)), 'EGL initialization failed'
        attributes = (C.c_int * 13)(0x3033, 1, 0x3040, 8, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
        config, count = C.c_void_p(), C.c_int()
        assert self.bind(self.egl, 'eglChooseConfig', C.c_uint, [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_void_p), C.c_int, C.POINTER(C.c_int)])(self.display, attributes, C.byref(config), 1, C.byref(count)) and count.value
        assert self.bind(self.egl, 'eglBindAPI', C.c_uint, [C.c_uint])(0x30A2)
        self.surface = self.bind(self.egl, 'eglCreatePbufferSurface', C.c_void_p, [C.c_void_p, C.c_void_p, C.POINTER(C.c_int)])(self.display, config, (C.c_int * 5)(0x3057, width, 0x3056, height, 0x3038))
        self.context = self.bind(self.egl, 'eglCreateContext', C.c_void_p, [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int)])(self.display, config, None, (C.c_int * 5)(0x3098, 3, 0x30FB, 3, 0x3038))
        self.make_current = self.bind(self.egl, 'eglMakeCurrent', C.c_uint, [C.c_void_p] * 4)
        assert self.surface and self.context and self.make_current(self.display, self.surface, self.surface, self.context), 'OpenGL context creation failed'
        self.renderer = self.bind(self.gl, 'glGetString', C.c_char_p, [C.c_uint])(0x1F01).decode()
        vertex = self.compile(0x8B31, '#version 330\nout vec2 v_uv;\nvoid main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);v_uv=p;gl_Position=vec4(p*2.0-1.0,0,1);}')
        fragment = self.compile(0x8B30, '#version 330\nin vec2 v_uv;out vec4 outColor;\n' + shader + '\nvoid main(){outColor=vec4(dynwall(vec2(v_uv.x,1.0-v_uv.y)),1.0);}')
        self.program = self.bind(self.gl, 'glCreateProgram', C.c_uint, [])()
        attach = self.bind(self.gl, 'glAttachShader', None, [C.c_uint, C.c_uint])
        attach(self.program, vertex)
        attach(self.program, fragment)
        self.bind(self.gl, 'glLinkProgram', None, [C.c_uint])(self.program)
        linked = C.c_int()
        self.bind(self.gl, 'glGetProgramiv', None, [C.c_uint, C.c_uint, C.POINTER(C.c_int)])(self.program, 0x8B82, C.byref(linked))
        assert linked.value, 'Shader program link failed'
        self.bind(self.gl, 'glUseProgram', None, [C.c_uint])(self.program)
        delete_shader = self.bind(self.gl, 'glDeleteShader', None, [C.c_uint])
        delete_shader(vertex)
        delete_shader(fragment)
        self.vao = C.c_uint()
        self.bind(self.gl, 'glGenVertexArrays', None, [C.c_int, C.POINTER(C.c_uint)])(1, C.byref(self.vao))
        self.bind(self.gl, 'glBindVertexArray', None, [C.c_uint])(self.vao)
        self.viewport = self.bind(self.gl, 'glViewport', None, [C.c_int] * 4)
        self.viewport(0, 0, width, height)
        self.locations = {}

    @staticmethod
    def bind(lib, name, result, args):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
        return fn

    def compile(self, kind, text):
        obj = self.bind(self.gl, 'glCreateShader', C.c_uint, [C.c_uint])(kind)
        encoded = C.c_char_p(text.encode())
        self.bind(self.gl, 'glShaderSource', None, [C.c_uint, C.c_int, C.POINTER(C.c_char_p), C.c_void_p])(obj, 1, C.byref(encoded), None)
        self.bind(self.gl, 'glCompileShader', None, [C.c_uint])(obj)
        ok = C.c_int()
        self.bind(self.gl, 'glGetShaderiv', None, [C.c_uint, C.c_uint, C.POINTER(C.c_int)])(obj, 0x8B81, C.byref(ok))
        log = C.create_string_buffer(65536)
        self.bind(self.gl, 'glGetShaderInfoLog', None, [C.c_uint, C.c_int, C.c_void_p, C.c_char_p])(obj, len(log), None, log)
        assert ok.value, log.value.decode()
        return obj

    def uniform(self, name, value):
        if name not in self.locations:
            self.locations[name] = self.bind(self.gl, 'glGetUniformLocation', C.c_int, [C.c_uint, C.c_char_p])(self.program, name.encode())
        location = self.locations[name]
        if location < 0:
            return
        values = value if isinstance(value, list) else [value]
        self.bind(self.gl, f'glUniform{len(values)}fv', None, [C.c_int, C.c_int, C.POINTER(C.c_float)])(location, 1, (C.c_float * len(values))(*values))

    def set(self, uniforms):
        for name, value in uniforms.items():
            self.uniform(name, value)

    def render(self):
        self.bind(self.gl, 'glDrawArrays', None, [C.c_uint, C.c_int, C.c_int])(4, 0, 3)
        self.bind(self.gl, 'glFinish', None, [])()
        pixels = (C.c_ubyte * (self.width * self.height * 4))()
        self.bind(self.gl, 'glReadPixels', None, [C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p])(0, 0, self.width, self.height, 0x1908, 0x1401, pixels)
        return Image.frombytes('RGBA', (self.width, self.height), bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB')

    def close(self):
        self.bind(self.gl, 'glDeleteProgram', None, [C.c_uint])(self.program)
        self.bind(self.gl, 'glDeleteVertexArrays', None, [C.c_int, C.POINTER(C.c_uint)])(1, C.byref(self.vao))
        self.make_current(self.display, None, None, None)
        self.bind(self.egl, 'eglDestroyContext', C.c_uint, [C.c_void_p, C.c_void_p])(self.display, self.context)
        self.bind(self.egl, 'eglDestroySurface', C.c_uint, [C.c_void_p, C.c_void_p])(self.display, self.surface)
        self.bind(self.egl, 'eglTerminate', C.c_uint, [C.c_void_p])(self.display)


def fixtures():
    def load(name):
        return json.loads(subprocess.check_output(['node', str(ROOT / 'tests' / name)], text=True))
    names = {f'{style}-{phase}' for style in ('ridges', 'alpine', 'dunes', 'ocean') for phase in ('day', 'dusk', 'night')}
    result = [f for f in load('renderer-fixtures.mjs') if f['name'] in names]
    result += [f for f in load('living-fixtures.mjs') if f['name'] in {'living-winter', 'living-spring', 'living-summer', 'living-autumn'}]
    assert len(result) == 16, 'Missing landscape fixture'
    return result


def run(args):
    shader = args.shader or ROOT / 'extension/weather.glsl'
    shader_text = shader.read_text()
    renderer = Renderer(args.width, args.height, shader_text, args.device)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'weather.glsl').write_text(shader_text)
    measurements = {'renderer': renderer.renderer, 'width': args.width, 'height': args.height,
                    'shader': str(shader), 'shader_sha256': hashlib.sha256(shader_text.encode()).hexdigest(),
                    'sky_reference_matches': [], 'stationary_land': [],
                    'partition_mean_delta': {}, 'median_frame_ms': {}}
    try:
        for fixture in fixtures():
            name = fixture['name']
            uniforms = {**NEUTRAL, **fixture['uniforms'], 'u_quality': {'low': 0, 'balanced': 1, 'high': 2}[args.quality],
                        'u_canvas': [args.width, args.height], 'u_view': [0, 0, args.width, args.height]}
            renderer.set(uniforms)
            image = renderer.render()
            image.save(args.output / f'{name}.png')
            assert max(ImageStat.Stat(image).stddev) > 2, f'Flat landscape: {name}'
            if args.reference_dir:
                expected = Image.open(args.reference_dir / f'{name}.png').convert('RGB')
                assert image.size == expected.size, f'Reference size differs: {name}'
                sky = (0, 0, args.width, int(args.height * .60))
                assert ImageChops.difference(image.crop(sky), expected.crop(sky)).getbbox() is None, f'Upper sky changed: {name}'
                measurements['sky_reference_matches'].append(name)
            samples = []
            for _ in range(args.benchmark_frames):
                start = time.perf_counter()
                renderer.render()
                samples.append((time.perf_counter() - start) * 1000)
            if samples:
                measurements['median_frame_ms'][name] = round(statistics.median(samples), 3)
            # Keep the same frozen art while disabling all time-varying weather.
            renderer.set({'u_coverage': 0, 'u_grain': 0, 'u_stars': 0, 'u_rain': 0, 'u_snow': 0,
                          'u_wind': [0, 0], 'u_flow': [0, 0], 'u_glowPulse': 0,
                          'u_celestialDrift': 0, 'u_time': 12})
            first = renderer.render()
            renderer.uniform('u_time', 1200)
            later = renderer.render()
            if not name.startswith('ocean-'):
                assert ImageChops.difference(first, later).getbbox() is None, f'Land or trees drift with time: {name}'
                measurements['stationary_land'].append(name)
            # Compare both monitor partitions against a single continuous canvas.
            renderer.set(uniforms)
            reference = renderer.render()
            deltas = []
            half = args.width // 2
            for offset, size in ((0, half), (half, args.width - half)):
                renderer.viewport(0, 0, size, args.height)
                renderer.uniform('u_view', [offset, 0, size, args.height])
                partition = renderer.render().crop((0, 0, size, args.height))
                expected = reference.crop((offset, 0, offset + size, args.height))
                difference = ImageChops.difference(partition, expected)
                delta = sum(ImageStat.Stat(difference).mean) / 3
                assert delta < .02, f'Monitor discontinuity: {name} {delta}'
                deltas.append(delta)
            measurements['partition_mean_delta'][name] = deltas
            renderer.viewport(0, 0, args.width, args.height)
            renderer.uniform('u_view', [0, 0, args.width, args.height])
            print(name, flush=True)
    finally:
        renderer.close()
    (args.output / 'measurements.json').write_text(json.dumps(measurements, indent=2) + '\n')
    print(json.dumps(measurements, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/dynwall-landscapes'))
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--device', type=int)
    parser.add_argument('--quality', choices=['low', 'balanced', 'high'], default='balanced')
    parser.add_argument('--shader', type=Path)
    parser.add_argument('--reference-dir', type=Path)
    parser.add_argument('--benchmark-frames', type=int, default=0)
    arguments = parser.parse_args()
    if min(arguments.width, arguments.height) < 2:
        parser.error('width and height must be at least 2')
    if arguments.benchmark_frames < 0:
        parser.error('benchmark frame count must be nonnegative')
    run(arguments)
