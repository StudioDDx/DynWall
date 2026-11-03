// No GNOME imports: this exact cache is unit-tested under Node.
// Shell.GLSLEffect receives C floats, so compare the values after the same
// float32 conversion and retain a private copy rather than caller-owned arrays.
export class UniformUploadCache {
    constructor() {
        this._values = new Map();
    }

    clear() {
        this._values.clear();
    }

    prepare(name, value) {
        const array = Array.isArray(value) ? value : null;
        const length = array ? array.length : 1;
        const previous = this._values.get(name);
        let same = previous?.length === length;
        for (let index = 0; same && index < length; index++) {
            const next = Math.fround(array ? array[index] : value);
            if (!Object.is(previous[index], next)) same = false;
        }
        if (same) return null;

        const next = Array.from({length}, (_, index) => Math.fround(array ? array[index] : value));
        this._values.set(name, next);
        return next;
    }
}
