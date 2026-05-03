/**
 * Abstract particle backdrop: luminous dots flowing toward center
 * on a dark gradient background.
 */
(function () {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const PARTICLE_COUNT = 120;
    const COLORS = [
        [96, 165, 250],   // blue
        [147, 197, 253],  // light blue
        [59, 130, 246],   // vivid blue
        [199, 210, 254],  // indigo-light
        [56, 189, 248],   // sky
    ];

    let W, H, cx, cy, dpr;
    let particles = [];
    let animId;
    let centralGlow = 0;

    function resize() {
        const parent = canvas.parentElement;
        const rect = parent
            ? { width: parent.clientWidth, height: parent.clientHeight }
            : { width: window.innerWidth, height: window.innerHeight };
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = rect.width;
        H = rect.height;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        cx = W / 2;
        cy = H / 2;
    }

    function spawnParticle(randomProgress) {
        const angle = Math.random() * Math.PI * 2;
        const maxR = Math.sqrt(W * W + H * H) * 0.55;
        const dist = maxR * (0.5 + Math.random() * 0.5);
        const color = COLORS[Math.floor(Math.random() * COLORS.length)];

        return {
            angle,
            dist,
            progress: randomProgress ? Math.random() : 0,
            speed: 0.001 + Math.random() * 0.003,
            size: 1 + Math.random() * 2.5,
            baseAlpha: 0.15 + Math.random() * 0.45,
            color,
            twinklePhase: Math.random() * Math.PI * 2,
            twinkleSpeed: 0.002 + Math.random() * 0.004,
            drift: (Math.random() - 0.5) * 0.3,
        };
    }

    function init() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push(spawnParticle(true));
        }
    }

    function drawBackground() {
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.7);
        grad.addColorStop(0, '#0f1729');
        grad.addColorStop(0.5, '#0c1220');
        grad.addColorStop(1, '#060a14');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);
    }

    function drawCentralGlow(time) {
        const pulse = Math.sin(time * 0.0015) * 0.15 + 0.85;
        const flash = centralGlow * 0.3;
        const r = 60 * pulse + flash * 40;

        // Soft outer glow
        const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 2.5);
        g1.addColorStop(0, `rgba(59, 130, 246, ${(0.08 + flash * 0.06) * pulse})`);
        g1.addColorStop(0.5, `rgba(37, 99, 235, ${(0.03 + flash * 0.03) * pulse})`);
        g1.addColorStop(1, 'rgba(37, 99, 235, 0)');
        ctx.fillStyle = g1;
        ctx.beginPath();
        ctx.arc(cx, cy, r * 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Core
        const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 0.5);
        g2.addColorStop(0, `rgba(147, 197, 253, ${0.12 + flash * 0.1})`);
        g2.addColorStop(1, 'rgba(59, 130, 246, 0)');
        ctx.fillStyle = g2;
        ctx.beginPath();
        ctx.arc(cx, cy, r * 0.5, 0, Math.PI * 2);
        ctx.fill();
    }

    function draw(time) {
        ctx.clearRect(0, 0, W, H);
        drawBackground();

        let absorbed = 0;

        particles.forEach((p) => {
            p.progress += p.speed;
            const t = p.progress;

            if (t >= 1) {
                absorbed++;
                Object.assign(p, spawnParticle(false));
                return;
            }

            // Position: lerp from spawn edge toward center
            const currentDist = p.dist * (1 - t * t); // ease-in toward center
            const currentAngle = p.angle + p.drift * t;
            const x = cx + Math.cos(currentAngle) * currentDist;
            const y = cy + Math.sin(currentAngle) * currentDist;

            // Twinkle
            const twinkle = Math.sin(time * p.twinkleSpeed + p.twinklePhase) * 0.3 + 0.7;

            // Fade in at start, fade out near center
            const fadeIn = Math.min(t * 6, 1);
            const fadeOut = t > 0.8 ? (1 - t) / 0.2 : 1;
            const alpha = p.baseAlpha * twinkle * fadeIn * fadeOut;

            // Size grows slightly as it approaches center
            const size = p.size * (1 + t * 0.8);

            const [r, g, b] = p.color;

            // Glow halo
            ctx.beginPath();
            ctx.arc(x, y, size * 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.1})`;
            ctx.fill();

            // Core dot
            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
            ctx.fill();

            // Bright center pixel
            if (size > 1.5) {
                ctx.beginPath();
                ctx.arc(x, y, size * 0.35, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.6})`;
                ctx.fill();
            }
        });

        // Central glow reacts to absorbed particles
        if (absorbed > 0) {
            centralGlow = Math.min(1, centralGlow + absorbed * 0.12);
        }
        centralGlow *= 0.94;

        drawCentralGlow(time);

        animId = requestAnimationFrame(draw);
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    resize();
    init();

    if (!prefersReducedMotion) {
        animId = requestAnimationFrame(draw);
    } else {
        draw(0);
        cancelAnimationFrame(animId);
    }

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            resize();
            init();
        }, 150);
    });
})();
