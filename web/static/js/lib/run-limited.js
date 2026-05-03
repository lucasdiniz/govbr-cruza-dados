// === lib/run-limited.js ===
async function runLimited(items, limit, worker) {
    const results = [];
    const queue = [...items];

    async function next() {
        const item = queue.shift();
        if (!item) return;
        results.push(await worker(item));
        await next();
    }

    await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => next()));
    return results;
}

