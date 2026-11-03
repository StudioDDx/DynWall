import Cogl from 'gi://Cogl';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';
import {UniformUploadCache} from './uniforms.js';

export const WeatherEffect = GObject.registerClass(
class DynwallWeatherEffect extends Shell.GLSLEffect {
    _init(source) {
        this._source = source;
        super._init();
        this._locations = new Map();
        this._uploads = new UniformUploadCache();
    }

    vfunc_build_pipeline() {
        // Pipeline rebuilds invalidate both Cogl locations and prior uniform state.
        this._locations?.clear();
        this._uploads?.clear();
        this.add_glsl_snippet(Cogl.SnippetHook.FRAGMENT, this._source,
            'cogl_color_out = vec4(dynwall(cogl_tex_coord_in[0].xy), 1.0) * cogl_color_in.a;', true);
    }

    update(uniforms) {
        for (const [name, value] of Object.entries(uniforms)) {
            const values = this._uploads.prepare(name, value);
            if (!values) continue;
            if (!this._locations.has(name))
                this._locations.set(name, this.get_uniform_location(name));
            const location = this._locations.get(name);
            if (location >= 0) {
                // GNOME 50 introspection: (location, components, values), no count argument.
                this.set_uniform_float(location, values.length, values);
            }
        }
        this.queue_repaint();
    }
});
