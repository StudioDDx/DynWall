import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as LoginManager from 'resource:///org/gnome/shell/misc/loginManager.js';
import {WeatherEffect} from './shader.js';
import {AutumnGusts, advanceAdvection, isAutumn, supportsWindborneLeaves} from './seasonal.js';
import {Lifetime, shouldAnimate, isInputChange, isDisplayAsleep} from './lifecycle.js';
import {sanitizeScene, weatherUniforms, monitorLayout, withCelestial} from './state.js';
import {resolvePresentation, transitionPresentation, sanitizePack, selectDocument, shouldResetEnvironment} from './presentation.js';
import {sanitizeLiving, seasonState, advanceEnvironment, rareMoments, performancePolicy, resolveSchedule, livingUniforms} from './living.js';

const UPowerProxy = Gio.DBusProxy.makeProxyWrapper(`<node>
<interface name="org.freedesktop.UPower"><property name="OnBattery" type="b" access="read"/></interface></node>`);

const MAX_DOCUMENT_BYTES = 128 * 1024;
const decode = bytes => new TextDecoder().decode(bytes);
const DisplayConfigProxy = Gio.DBusProxy.makeProxyWrapper(`<node>
<interface name="org.gnome.Mutter.DisplayConfig">
<property name="PowerSaveMode" type="i" access="read"/>
</interface></node>`);

function readDocument(path) {
    try {
        const file = Gio.File.new_for_path(path);
        const info = file.query_info('standard::size,standard::type', Gio.FileQueryInfoFlags.NONE, null);
        if (info.get_file_type() !== Gio.FileType.REGULAR || info.get_size() > MAX_DOCUMENT_BYTES)
            return null;
        const [ok, bytes] = file.load_contents(null);
        if (!ok || bytes.length > MAX_DOCUMENT_BYTES) return null;
        return JSON.parse(decode(bytes));
    } catch (_) {
        // Missing, half-replaced, and malformed documents expose the static fallback.
        return null;
    }
}

export default class DynwallExtension extends Extension {
    enable() {
        this._life = new Lifetime(error => console.error(`[Dynwall] Cleanup: ${error.message}`));
        this._frameSource = 0;
        this._reloadSource = 0;
        this._elapsed = 0;
        this._flow = [0, 0];
        this._gusts = new AutumnGusts();
        this._effects = [];
        this._current = null;
        this._suspended = false;
        this._displayAsleep = false;
        this._onBattery = false;
        this._packKey = null;
        this._environment = null;
        this._resetGeneration = null;
        this._frameCpuMs = 0;
        this._lastFrame = GLib.get_monotonic_time();
        this._nextRead = 0;
        try {
            const [ok, bytes] = this.dir.get_child('weather.glsl').load_contents(null);
            if (!ok) throw new Error('The weather shader could not be read');
            this._shader = decode(bytes);
            const cache = GLib.get_user_cache_dir();
            this._scenePath = GLib.build_filenamev([cache, 'dynwall', 'scene.json']);
            this._weatherPath = GLib.build_filenamev([cache, 'topweather', 'current.json']);
            this._previewPath = GLib.build_filenamev([cache, 'dynwall', 'preview.json']);
            this._environmentPath = GLib.build_filenamev([cache, 'dynwall', 'environment.json']);
            this._resetPath = GLib.build_filenamev([cache, 'dynwall', 'environment-reset.json']);
            this._environment = readDocument(this._environmentPath);
            this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
            this._login = LoginManager.getLoginManager();
            this._suspended = this._login.preparingForSleep;
            this._connect(Main.layoutManager, 'monitors-changed', () => this._guard(() => {
                this._destroyActors(); this._reload();
            }));
            this._connect(Main.overview, 'showing', () => this._guard(() => this._sync()));
            this._connect(Main.overview, 'hidden', () => this._guard(() => this._reload()));
            this._connect(Main.screenShield, 'locked-changed', () => this._guard(() => this._reload()));
            this._connect(this._settings, 'changed::enable-animations', () => this._guard(() => this._reload()));
            this._connect(this._login, 'prepare-for-sleep', (_manager, suspended) => {
                this._suspended = suspended;
                this._guard(() => this._reload());
            });
            this._monitors = [];
            // Watch both parents and their cache root: creation of a missing provider dir is visible.
            this._watchDirectory(cache);
            this._watchInputs();
            this._life.add(() => this._destroyActors());
            this._life.add(() => this._stopFrame());
            this._life.add(() => {
                if (this._reloadSource) GLib.Source.remove(this._reloadSource);
                this._reloadSource = 0;
            });
            this._watchDisplayPower();
            this._watchBattery();
            this._connect(global.display, 'in-fullscreen-changed', () => this._guard(() => this._sync()));
            this._reload();
        } catch (error) {
            this._fail(error);
        }
    }

    _connect(object, signal, callback) {
        const id = object.connect(signal, callback);
        this._life.add(() => object.disconnect(id));
    }

    _watchDisplayPower() {
        const life = this._life;
        const cancellable = new Gio.Cancellable();
        life.add(() => cancellable.cancel());
        // DisplayConfig belongs to this same Shell process. Synchronous proxy
        // initialization can deadlock the compositor while waiting on itself.
        new DisplayConfigProxy(Gio.DBus.session, 'org.gnome.Mutter.DisplayConfig',
            '/org/gnome/Mutter/DisplayConfig', (proxy, error) => {
                if (life.closed || this._life !== life || error) return;
                const sync = () => this._guard(() => {
                    this._displayAsleep = isDisplayAsleep(proxy.get_cached_property('PowerSaveMode')?.deep_unpack());
                    this._sync();
                });
                this._connect(proxy, 'g-properties-changed', sync);
                sync();
            }, cancellable);
    }

    _watchBattery() {
        const life = this._life;
        const cancellable = new Gio.Cancellable();
        life.add(() => cancellable.cancel());
        try {
            new UPowerProxy(Gio.DBus.system, 'org.freedesktop.UPower', '/org/freedesktop/UPower',
            (proxy, error) => {
                if (life.closed || this._life !== life || error) return;
                const sync = () => this._guard(() => {
                    this._onBattery = proxy.get_cached_property('OnBattery')?.deep_unpack() === true;
                    this._sync();
                });
                this._connect(proxy, 'g-properties-changed', sync);
                sync();
            }, cancellable, Gio.DBusProxyFlags.DO_NOT_AUTO_START);
        } catch (_) {
            // A missing system bus/UPower is optional, just like an unknown battery.
            this._onBattery = false;
        }
    }

    _writeEnvironment() {
        if (!this._environment || this._presentation?.preview) return;
        try {
            const directory = Gio.File.new_for_path(GLib.path_get_dirname(this._environmentPath));
            if (!directory.query_exists(null)) directory.make_directory_with_parents(null);
            Gio.File.new_for_path(this._environmentPath).replace_contents(
                new TextEncoder().encode(JSON.stringify(this._environment)), null, false,
                Gio.FileCreateFlags.PRIVATE | Gio.FileCreateFlags.REPLACE_DESTINATION, null);
        } catch (error) {
            // A read-only cache never disables the live sky. State remains bounded in memory.
            console.warn(`[Dynwall] Environment state not saved: ${error.message}`);
        }
    }

    _fullscreenMonitors() {
        return Main.layoutManager.monitors.map((_, index) => {
            try { return global.display.get_monitor_in_fullscreen(index); }
            catch (_) { return false; }
        });
    }

    _loadPack(descriptor) {
        const pack = sanitizePack(descriptor);
        if (!pack) return null;
        try {
            const file = Gio.File.new_for_path(pack.foreground);
            const info = file.query_info('standard::size,standard::type,standard::is-symlink',
                Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, null);
            if (info.get_is_symlink() || info.get_file_type() !== Gio.FileType.REGULAR || info.get_size() > 32 * 1024 * 1024) return null;
            const [, width, height] = GdkPixbuf.Pixbuf.get_file_info(pack.foreground);
            if (!width || !height || width > 8192 || height > 8192 || width * height > 33554432) return null;
            const pixels = GdkPixbuf.Pixbuf.new_from_file(pack.foreground);
            const content = St.ImageContent.new_with_preferred_size(pixels.width, pixels.height);
            const context = global.stage.get_context().get_backend().get_cogl_context();
            if (!content.set_bytes(context, new GLib.Bytes(pixels.get_pixels()),
                pixels.get_has_alpha() ? Cogl.PixelFormat.RGBA_8888 : Cogl.PixelFormat.RGB_888,
                pixels.width, pixels.height, pixels.rowstride)) return null;
            return content;
        } catch (_) { return null; }
    }

    _watchDirectory(path) {
        if (this._monitors.some(item => item.path === path)) return;
        try {
            const monitor = Gio.File.new_for_path(path).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
            this._monitors.push({path, monitor});
            this._connect(monitor, 'changed', (_monitor, file, otherFile) => {
                if (isInputChange(file?.get_basename(), otherFile?.get_basename()) ||
                    ['preview.json', 'environment-reset.json'].some(name => name === file?.get_basename() || name === otherFile?.get_basename()))
                    this._queueReload();
            });
            this._life.add(() => monitor.cancel());
        } catch (_) {
            // Parent watcher retries when a not-yet-created cache directory appears.
        }
    }

    _watchInputs() {
        for (const path of [this._scenePath, this._weatherPath, this._previewPath])
            this._watchDirectory(GLib.path_get_dirname(path));
    }

    _queueReload() {
        if (!this._life || this._life.closed || this._reloadSource) return;
        this._reloadSource = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._reloadSource = 0;
            this._guard(() => { this._watchInputs(); this._reload(); });
            return GLib.SOURCE_REMOVE;
        });
    }

    _reload() {
        if (!this._life || this._life.closed) return;
        const now = Date.now();
        let document = readDocument(this._scenePath);
        this._scene = sanitizeScene(document, now);
        // The live file is authoritative. Never resurrect an invalidated location from scene.weather.
        let snapshot = readDocument(this._weatherPath);
        if (!snapshot || snapshot.schemaVersion !== 1 || !Number.isFinite(snapshot.fetchedAt) ||
            now - snapshot.fetchedAt > 7200000 || snapshot.fetchedAt > now + 300000)
            snapshot = null;
        const request = readDocument(this._previewPath);
        const scheduled = resolveSchedule(document?.living ?? {}, now);
        document = selectDocument(document, scheduled, now);
        this._presentation = resolvePresentation(document, request, snapshot, now);
        const previewIdentity = this._presentation.preview ? JSON.stringify(request) : 'live';
        if (previewIdentity !== this._previewIdentity) {
            // A preview is a separate presentation, never an interpolated live observation.
            this._current = null;
            this._previewIdentity = previewIdentity;
        }
        document = this._presentation.document;
        this._scene = sanitizeScene(document, now);
        this._snapshot = snapshot;
        this._clock = this._presentation.clock;
        const displayedWeather = this._presentation.snapshot;
        this._livingDocument = document?.living ?? {};
        this._living = sanitizeLiving(this._livingDocument);
        const reset = readDocument(this._resetPath)?.generatedAt;
        if (Number.isFinite(reset) && reset !== this._resetGeneration) {
            this._resetGeneration = reset;
            if (shouldResetEnvironment(this._environment, reset)) this._environment = null;
        }
        // Synthetic scenarios never enter persistent state.
        if (!this._presentation.preview) {
            this._environment = advanceEnvironment(this._environment,
                this._living.persistent_weather ? snapshot : null, now);
            if (!this._living.persistent_weather) this._environment = {...this._environment, snow: 0, wetness: 0};
            this._writeEnvironment();
        }
        this._season = this._scene?.seasonalEffects ? seasonState(this._clock, snapshot?.latitude) : null;
        const descriptor = this._livingDocument.landscape_enabled === false ? null : document?.packs?.[this._livingDocument.landscape_pack];
        const packKey = JSON.stringify([descriptor ?? null, this._livingDocument.scene_customization ?? null]);
        if (this._packKey !== packKey) {
            this._packKey = packKey;
            this._packContent = this._loadPack(descriptor);
            this._packDescriptor = sanitizePack(descriptor);
            this._destroyActors();
        }
        this._target = this._scene ? {
            ...withCelestial(this._scene.uniforms, displayedWeather, this._clock), ...weatherUniforms(displayedWeather, this._clock),
        } : null;
        if (this._target && this._packContent)
            this._target.u_landscape = [0, ...this._target.u_landscape.slice(1)];
        this._autumnEnabled = !!this._scene?.seasonalEffects && isAutumn(this._clock, snapshot?.latitude);
        this._nextRead = GLib.get_monotonic_time() + 15000000;
        if (!this._scene?.enabled) {
            this._current = null;
            this._destroyActors();
        }
        this._sync();
    }

    _sync() {
        if (!this._life || this._life.closed) return;
        const animations = this._settings.get_boolean('enable-animations');
        this._policy = performancePolicy({fps: this._scene?.fps, quality: this._scene?.quality,
            onBattery: this._onBattery, batterySaver: this._living?.battery_saver,
            fullscreenMonitors: this._fullscreenMonitors(), locked: Main.screenShield.locked,
            suspended: this._suspended, displayAsleep: this._displayAsleep, reducedMotion: !animations});
        const running = !this._policy.paused && this._living?.scene_customization?.animation_intensity !== 0 && shouldAnimate({enabled: this._scene?.enabled, hasScene: !!this._target,
            hasMonitors: Main.layoutManager.monitors.length > 0,
            animations,
            locked: Main.screenShield.locked, suspended: this._suspended,
            displayAsleep: this._displayAsleep,
            overview: Main.overview.visible || Main.overview.animationInProgress});
        if (!running) {
            this._stopFrame();
            this._group?.hide();
            return;
        }
        if (!this._group) this._createActors();
        this._group?.show();
        for (const [index, {actor}] of this._effects.entries())
            actor.visible = this._policy.visibleMonitors[index] !== false;
        const interval = Math.ceil(1000 / this._policy.fps);
        if (this._frameSource && interval === this._interval) return;
        this._stopFrame();
        this._interval = interval;
        this._lastFrame = GLib.get_monotonic_time();
        this._draw(0);
        this._frameSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT_IDLE, interval, () => {
            // Own the source ID until it is actually removed; errors and pause both remove it.
            try {
                const now = GLib.get_monotonic_time();
                if (now >= this._nextRead) this._reload();
                if (!this._frameSource || !this._group) return GLib.SOURCE_REMOVE;
                const dt = Math.min(.2, Math.max(0, (now - this._lastFrame) / 1000000));
                this._lastFrame = now;
                this._draw(dt);
                return GLib.SOURCE_CONTINUE;
            } catch (error) {
                this._frameSource = 0;
                this._fail(error);
                return GLib.SOURCE_REMOVE;
            }
        });
    }

    _createActors() {
        const bounds = monitorLayout(Main.layoutManager.monitors);
        if (!bounds) return;
        const group = new Clutter.Actor({name: 'Dynwall GPU Weather', reactive: false});
        this._group = group;
        this._bounds = bounds;
        // Keep weather INSIDE the background group. Mutter restacks window actors
        // below arbitrary non-window siblings, so a direct window_group child can
        // cover applications even when initially inserted below them.
        Main.layoutManager._backgroundGroup.add_child(group);
        try {
            for (const monitor of Main.layoutManager.monitors) {
                const black = new Cogl.Color();
                black.init_from_4f(0, 0, 0, 1);
                const actor = new Clutter.Actor({name: 'Dynwall weather monitor', reactive: false,
                    x: monitor.x, y: monitor.y, width: monitor.width, height: monitor.height,
                    background_color: black});
                group.add_child(actor);
                const effect = new WeatherEffect(this._shader);
                actor.add_effect(effect);
                this._effects.push({actor, effect, view: [monitor.x - bounds.x, monitor.y - bounds.y, monitor.width, monitor.height]});
            }
            if (this._packContent) {
                const controls = this._livingDocument.scene_customization ?? {};
                const scale = Number.isFinite(controls.terrain_scale) ? Math.max(.5, Math.min(2, controls.terrain_scale)) : 1;
                const horizon = Number.isFinite(controls.horizon) ? controls.horizon : .8;
                const original = this._packDescriptor.horizon;
                const shift = original + horizon - .8 - original * scale;
                const foreground = new Clutter.Actor({name: 'Dynwall landscape pack', reactive: false,
                    x: bounds.x, y: bounds.y + bounds.height * shift, width: bounds.width,
                    height: bounds.height * scale, content: this._packContent,
                    content_gravity: Clutter.ContentGravity.RESIZE_FILL, opacity: 0});
                group.add_child(foreground);
                foreground.ease({opacity: 255, duration: 600, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
            }
        } catch (error) {
            this._destroyActors();
            throw error;
        }
    }

    _draw(dt) {
        this._current = this._current ? transitionPresentation(this._current, this._target, dt) : this._target;
        const cpuStart = GLib.get_monotonic_time();
        const intensity = this._living?.scene_customization?.animation_intensity ?? 1;
        dt *= intensity;
        this._elapsed += dt;
        const leafSource = supportsWindborneLeaves(this._target.u_landscape[0], !!this._packContent);
        const leaves = this._gusts.update(dt, {
            enabled: this._autumnEnabled && leafSource, windX: this._current.u_wind[0],
        });
        // Integrate wind to avoid a position discontinuity when weather direction/speed changes.
        // Decorative gusts never alter the authoritative weather uniforms.
        this._flow = advanceAdvection(this._flow, this._current.u_wind, leaves, dt);
        const quality = {low: 0, balanced: 1, high: 2}[this._policy?.quality ?? this._scene.quality];
        const eventClock = this._presentation.preview ? this._clock + this._elapsed * 1000 : Date.now();
        const moments = rareMoments(eventClock, {enabled: intensity > 0,
            intensity: this._living.atmospheric_intensity, reducedMotion: !this._settings.get_boolean('enable-animations'),
            daylight: this._current.u_daylight, coverage: this._current.u_coverage, rain: this._current.u_rain,
            season: this._season, latitude: this._snapshot?.latitude});
        const environment = this._living.persistent_weather ?
            (this._presentation.preview ? this._presentation.environment : this._environment) : null;
        const additions = livingUniforms(this._living, environment, this._season, moments);
        for (const {actor, effect, view} of this._effects) {
            if (!actor.visible) continue;
            effect.update({...this._current, ...additions, u_canvas: [this._bounds.width, this._bounds.height],
                u_view: view, u_time: this._elapsed, u_flow: this._flow, u_quality: quality,
                u_leaves: leaves,
                // Honor the user's landscape switch immediately, independently
                // of the slow interpolation used for changing weather and light.
                u_landscape: this._target.u_landscape});
        }
        // CPU submission duration is not GPU utilization or GPU frame duration.
        this._frameCpuMs = (GLib.get_monotonic_time() - cpuStart) / 1000;
    }

    _stopFrame() {
        if (this._frameSource) GLib.Source.remove(this._frameSource);
        this._frameSource = 0;
    }

    _destroyActors() {
        this._effects = [];
        this._group?.destroy();
        this._group = null;
    }

    _guard(callback) {
        try { callback(); } catch (error) { this._fail(error); }
    }

    _fail(error) {
        console.error(`[Dynwall] GPU renderer stopped; static wallpaper retained: ${error.message}`);
        this.disable();
    }

    disable() {
        this._life?.close();
        this._life = null;
        this._scene = this._target = this._current = this._shader = null;
        this._settings = this._login = null;
        this._gusts = null;
        this._packContent = this._packDescriptor = this._living = this._season = this._policy = null;
        this._monitors = [];
    }
}
