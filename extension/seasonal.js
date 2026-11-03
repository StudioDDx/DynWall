// Decorative events use active animation time, never weather timestamps or timers.
const QUIET = Object.freeze([0, 0, 0, 0]);
const finite = value => Number.isFinite(value) ? value : 0;
const smooth = value => {
    const t = Math.max(0, Math.min(1, value));
    return t * t * (3 - 2 * t);
};

export function isAutumn(now, latitude) {
    const month = new Date(now).getMonth();
    const south = Number.isFinite(latitude) && latitude < 0;
    return south ? month >= 2 && month <= 4 : month >= 8 && month <= 10;
}

export function supportsWindborneLeaves(landscapeStyle, hasForegroundPack = false) {
    return hasForegroundPack === true || (landscapeStyle > .5 && landscapeStyle < 2.5);
}

export function advanceAdvection(flow, wind, leaves, seconds) {
    const dt = Math.max(0, Math.min(.2, finite(seconds)));
    const gust = finite(leaves?.[1]) * finite(leaves?.[2]) * 18;
    return [0, 1].map(index => finite(flow?.[index]) +
        (finite(wind?.[index]) + (index === 0 ? gust : 0)) * dt * .0015);
}

export class AutumnGusts {
    constructor(random = Math.random) {
        this._random = random;
        this._enabled = false;
        this._reset();
    }

    _reset() {
        this._wait = 12 + this._random() * 23;
        this._age = null;
    }

    // [active seconds, fade envelope, horizontal direction, per-event seed].
    update(seconds, {enabled = false, windX = 0} = {}) {
        if (!enabled) {
            if (this._enabled) this._reset();
            this._enabled = false;
            return QUIET;
        }
        this._enabled = true;
        const dt = Number.isFinite(seconds) ? Math.max(0, Math.min(.2, seconds)) : 0;
        if (this._age === null) {
            this._wait -= dt;
            if (this._wait > 0) return QUIET;
            this._age = -this._wait;
            this._duration = 10 + this._random() * 8;
            this._direction = Number.isFinite(windX) && Math.abs(windX) > .2
                ? Math.sign(windX) : (this._random() < .5 ? -1 : 1);
            this._seed = this._random() * 100;
        } else {
            this._age += dt;
        }
        if (this._age >= this._duration) {
            this._age = null;
            this._wait = 90 + this._random() * 150;
            return QUIET;
        }
        return [this._age, smooth(this._age / 2) * smooth((this._duration - this._age) / 3),
            this._direction, this._seed];
    }
}
