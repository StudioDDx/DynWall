/** Own only our resources; disposal cannot strand an actor after one native error. */
export class Lifetime {
    constructor(onError = () => {}) {
        this.closed = false;
        this._disposers = [];
        this._onError = onError;
    }
    add(dispose) {
        if (this.closed) {
            try { dispose(); } catch (error) { this._onError(error); }
        } else {
            this._disposers.push(dispose);
        }
        return dispose;
    }
    close() {
        if (this.closed) return;
        this.closed = true;
        for (const dispose of this._disposers.reverse()) {
            try { dispose(); } catch (error) { this._onError(error); }
        }
        this._disposers = [];
    }
}

export function shouldAnimate(flags) {
    return Boolean(flags.enabled && flags.hasScene && flags.hasMonitors && flags.animations &&
        !flags.locked && !flags.suspended && !flags.overview && !flags.displayAsleep);
}

// Unknown/unsupported power state must not accidentally disable a visible sky.
export function isDisplayAsleep(mode) {
    return mode === 1 || mode === 2 || mode === 3;
}

/** Gio WATCH_MOVES RENAMED carries the atomic destination in other_file. */
export function isInputChange(fileName, otherFileName) {
    const names = ['scene.json', 'current.json', 'dynwall', 'topweather'];
    return names.includes(fileName) || names.includes(otherFileName);
}
