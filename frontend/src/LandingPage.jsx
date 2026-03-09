import { useState, useEffect, useRef, useCallback } from 'react';

function LandingPage({ onEnter }) {
    const canvasRef = useRef(null);
    const [typedText, setTypedText] = useState('');
    const [showContent, setShowContent] = useState(false);
    const [isExiting, setIsExiting] = useState(false);
    const [visibleSections, setVisibleSections] = useState({});
    const fullText = 'Transform Documents into Living Knowledge';

    // Intersection Observer for scroll reveals
    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setVisibleSections((prev) => ({ ...prev, [entry.target.id]: true }));
                    }
                });
            },
            { threshold: 0.15, rootMargin: '0px 0px -50px 0px' }
        );
        document.querySelectorAll('[data-reveal]').forEach((el) => observer.observe(el));
        return () => observer.disconnect();
    }, [showContent]);

    // Typing animation
    useEffect(() => {
        setTimeout(() => setShowContent(true), 200);
        let i = 0;
        const timer = setInterval(() => {
            if (i <= fullText.length) {
                setTypedText(fullText.slice(0, i));
                i++;
            } else {
                clearInterval(timer);
            }
        }, 40);
        return () => clearInterval(timer);
    }, []);

    // Premium particle canvas — subtle floating orbs
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let animationId;
        let mouse = { x: -500, y: -500 };

        const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight * 3; };
        resize();
        window.addEventListener('resize', resize);
        const handleMouseMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY + window.scrollY; };
        window.addEventListener('mousemove', handleMouseMove);

        const orbs = [];
        for (let i = 0; i < 60; i++) {
            orbs.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                r: Math.random() * 2 + 0.8,
                hue: [200, 220, 260, 280, 170][Math.floor(Math.random() * 5)],
                alpha: Math.random() * 0.4 + 0.1,
                phase: Math.random() * Math.PI * 2,
            });
        }

        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const t = Date.now() * 0.001;

            orbs.forEach((p, i) => {
                const dx = p.x - mouse.x;
                const dy = p.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 120) {
                    p.vx += (dx / dist) * 0.15;
                    p.vy += (dy / dist) * 0.15;
                }
                p.x += p.vx; p.y += p.vy;
                p.vx *= 0.995; p.vy *= 0.995;
                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

                const pulse = Math.sin(t * 1.5 + p.phase) * 0.3 + 0.7;
                const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
                grd.addColorStop(0, `hsla(${p.hue}, 80%, 65%, ${p.alpha * pulse})`);
                grd.addColorStop(1, `hsla(${p.hue}, 80%, 65%, 0)`);
                ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
                ctx.fillStyle = grd; ctx.fill();
                ctx.beginPath(); ctx.arc(p.x, p.y, p.r * pulse, 0, Math.PI * 2);
                ctx.fillStyle = `hsla(${p.hue}, 90%, 75%, ${p.alpha * pulse * 0.8})`;
                ctx.fill();

                orbs.forEach((p2, j) => {
                    if (j <= i) return;
                    const d = Math.hypot(p.x - p2.x, p.y - p2.y);
                    if (d < 160) {
                        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y);
                        ctx.strokeStyle = `hsla(210, 60%, 50%, ${(1 - d / 160) * 0.06})`;
                        ctx.lineWidth = 0.5; ctx.stroke();
                    }
                });
            });
            animationId = requestAnimationFrame(animate);
        };
        animate();
        return () => { cancelAnimationFrame(animationId); window.removeEventListener('resize', resize); window.removeEventListener('mousemove', handleMouseMove); };
    }, []);

    const handleEnter = useCallback(() => {
        setIsExiting(true);
        setTimeout(() => onEnter(), 700);
    }, [onEnter]);

    const features = [
        { icon: '📄', title: 'PDF Intelligence', desc: 'Upload any document and watch AI extract entities, concepts, and hidden relationships automatically.', gradient: 'linear-gradient(135deg, #667eea, #764ba2)' },
        { icon: '🌐', title: '3D Knowledge Graph', desc: 'Explore interactive 3D force-directed graphs powered by Three.js with real-time physics simulation.', gradient: 'linear-gradient(135deg, #00d2ff, #3a7bd5)' },
        { icon: '🤖', title: 'Neural Chat', desc: 'Query your knowledge graph with natural language. Get context-aware answers with transparent reasoning.', gradient: 'linear-gradient(135deg, #f093fb, #f5576c)' },
        { icon: '🧠', title: 'Graph Analytics', desc: 'AI-powered analysis detecting hub nodes, knowledge clusters, bridge concepts, and hidden patterns.', gradient: 'linear-gradient(135deg, #4facfe, #00f2fe)' },
    ];

    const s = (cond, base, active) => ({ ...base, ...(cond ? active : {}) });
    const reveal = (id, delay = 0) => ({
        opacity: visibleSections[id] ? 1 : 0,
        transform: visibleSections[id] ? 'translateY(0)' : 'translateY(40px)',
        transition: `all 0.9s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s`,
    });

    return (
        <div style={{
            width: '100vw', background: '#09090f', position: 'relative',
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            transition: 'opacity 0.7s ease, transform 0.7s ease',
            opacity: isExiting ? 0 : 1, transform: isExiting ? 'scale(1.02)' : 'scale(1)',
            overflowX: 'hidden',
        }}>
            <canvas ref={canvasRef} style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0, opacity: 0.7 }} />

            {/* Mesh gradient blobs */}
            <div style={{ position: 'fixed', top: '-20%', right: '-10%', width: '600px', height: '600px', background: 'radial-gradient(circle, rgba(102, 126, 234, 0.08) 0%, transparent 70%)', zIndex: 1, pointerEvents: 'none', filter: 'blur(60px)' }} />
            <div style={{ position: 'fixed', bottom: '-10%', left: '-10%', width: '500px', height: '500px', background: 'radial-gradient(circle, rgba(118, 75, 162, 0.06) 0%, transparent 70%)', zIndex: 1, pointerEvents: 'none', filter: 'blur(60px)' }} />
            <div style={{ position: 'fixed', top: '40%', left: '30%', width: '400px', height: '400px', background: 'radial-gradient(circle, rgba(0, 210, 255, 0.04) 0%, transparent 70%)', zIndex: 1, pointerEvents: 'none', filter: 'blur(80px)' }} />

            {/* Navbar */}
            <nav style={{
                position: 'fixed', top: 0, left: 0, right: 0, zIndex: 1000,
                padding: '0 clamp(20px, 5vw, 60px)',
                height: '72px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'rgba(9, 9, 15, 0.7)', backdropFilter: 'blur(24px) saturate(180%)',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(-20px)',
                transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '10px', background: 'linear-gradient(135deg, #667eea, #764ba2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px' }}>🧠</div>
                    <span style={{ fontSize: '18px', fontWeight: '800', color: '#f0f0f5', letterSpacing: '-0.3px' }}>GraphMind</span>
                </div>
                <div style={{ display: 'flex', gap: '32px', alignItems: 'center' }}>
                    {['Features', 'Process', 'About'].map(t => (
                        <a key={t} href={`#${t.toLowerCase()}`} style={{ color: 'rgba(255,255,255,0.45)', textDecoration: 'none', fontSize: '13.5px', fontWeight: '500', transition: 'color 0.3s', letterSpacing: '0.2px' }}
                            onMouseEnter={e => e.target.style.color = '#fff'} onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.45)'}>{t}</a>
                    ))}
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', color: '#fff',
                        padding: '9px 22px', borderRadius: '10px', fontWeight: '600', fontSize: '13px', cursor: 'pointer',
                        transition: 'all 0.3s', boxShadow: '0 2px 12px rgba(102, 126, 234, 0.25)',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'translateY(-1px)'; e.target.style.boxShadow = '0 4px 20px rgba(102, 126, 234, 0.4)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 2px 12px rgba(102, 126, 234, 0.25)'; }}
                    >Open App</button>
                </div>
            </nav>

            {/* Hero */}
            <section style={{ position: 'relative', zIndex: 10, minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: '120px 24px 80px' }}>
                <div style={{ opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(30px)', transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.2s' }}>
                    <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '7px 18px', borderRadius: '100px',
                        background: 'rgba(102, 126, 234, 0.08)', border: '1px solid rgba(102, 126, 234, 0.15)',
                        fontSize: '12.5px', color: 'rgba(255,255,255,0.7)', fontWeight: '500', marginBottom: '32px',
                    }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#667eea', boxShadow: '0 0 8px #667eea' }} />
                        AI-Powered Knowledge Graph Engine
                    </div>
                </div>

                <h1 style={{
                    fontSize: 'clamp(38px, 5.5vw, 74px)', fontWeight: '800', color: '#f0f0f5',
                    lineHeight: 1.08, maxWidth: '820px', margin: '0 0 24px 0', letterSpacing: '-2px',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(30px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.4s',
                }}>
                    {typedText}<span style={{ color: '#667eea', animation: 'cursorBlink 1s step-end infinite', fontWeight: '200' }}>|</span>
                </h1>

                <p style={{
                    fontSize: 'clamp(16px, 1.8vw, 19px)', color: 'rgba(255,255,255,0.4)', maxWidth: '540px', lineHeight: 1.7, margin: '0 0 48px 0', fontWeight: '400',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(30px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.6s',
                }}>
                    Upload PDFs. Extract entities & relationships. Explore knowledge in immersive 3D — powered by NVIDIA Nemotron AI.
                </p>

                <div style={{
                    display: 'flex', gap: '14px', flexWrap: 'wrap', justifyContent: 'center',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(30px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.8s',
                }}>
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', color: '#fff',
                        padding: '16px 40px', borderRadius: '14px', fontWeight: '700', fontSize: '15px', cursor: 'pointer',
                        boxShadow: '0 4px 25px rgba(102, 126, 234, 0.3), inset 0 1px 0 rgba(255,255,255,0.15)',
                        transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)', letterSpacing: '0.3px',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'translateY(-3px)'; e.target.style.boxShadow = '0 8px 40px rgba(102, 126, 234, 0.45)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 4px 25px rgba(102, 126, 234, 0.3)'; }}
                    >Get Started Free →</button>
                    <a href="https://github.com/sricharanreddynyayam-crypto/GraphMind" target="_blank" rel="noreferrer" style={{
                        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                        color: 'rgba(255,255,255,0.6)', padding: '16px 32px', borderRadius: '14px',
                        fontWeight: '600', fontSize: '14px', cursor: 'pointer', textDecoration: 'none',
                        transition: 'all 0.3s', display: 'inline-flex', alignItems: 'center', gap: '8px',
                    }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#fff'; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'rgba(255,255,255,0.6)'; }}
                    >View on GitHub</a>
                </div>

                {/* Trusted by strip */}
                <div style={{
                    marginTop: '90px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px',
                    opacity: showContent ? 1 : 0, transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 1.2s',
                }}>
                    <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)', letterSpacing: '2.5px', fontWeight: '600', textTransform: 'uppercase' }}>Built With</span>
                    <div style={{ display: 'flex', gap: '40px', alignItems: 'center', opacity: 0.25 }}>
                        {['React', 'FastAPI', 'Three.js', 'NVIDIA AI', 'NetworkX'].map(t => (
                            <span key={t} style={{ fontSize: '14px', color: '#fff', fontWeight: '600', letterSpacing: '0.5px' }}>{t}</span>
                        ))}
                    </div>
                </div>
            </section>

            {/* Features - Bento Grid */}
            <section id="features" data-reveal style={{ position: 'relative', zIndex: 10, padding: '100px clamp(20px, 5vw, 60px)', maxWidth: '1100px', margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: '60px', ...reveal('features') }}>
                    <span style={{ fontSize: '12px', color: '#667eea', letterSpacing: '3px', fontWeight: '600', textTransform: 'uppercase' }}>Features</span>
                    <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: '800', color: '#f0f0f5', margin: '12px 0 0 0', letterSpacing: '-1px' }}>
                        Everything you need to <br />
                        <span style={{ background: 'linear-gradient(135deg, #667eea, #764ba2, #f093fb)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>understand your data</span>
                    </h2>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                    {features.map((f, i) => (
                        <div key={i} id={`feat-${i}`} data-reveal style={{
                            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
                            borderRadius: '20px', padding: '36px 32px', cursor: 'default',
                            transition: 'all 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
                            backdropFilter: 'blur(10px)',
                            ...reveal(`feat-${i}`, i * 0.1),
                        }}
                            onMouseEnter={e => {
                                e.currentTarget.style.transform = 'translateY(-4px)';
                                e.currentTarget.style.borderColor = 'rgba(102, 126, 234, 0.15)';
                                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)';
                                e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                            }}
                        >
                            <div style={{
                                width: '48px', height: '48px', borderRadius: '14px', background: f.gradient,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '22px', marginBottom: '20px', boxShadow: `0 4px 15px ${f.gradient.includes('667eea') ? 'rgba(102,126,234,0.2)' : 'rgba(0,0,0,0.2)'}`,
                            }}>{f.icon}</div>
                            <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#e8e8ed', margin: '0 0 10px 0', letterSpacing: '-0.3px' }}>{f.title}</h3>
                            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.35)', lineHeight: 1.7, margin: 0 }}>{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Process Section */}
            <section id="process" data-reveal style={{ position: 'relative', zIndex: 10, padding: '100px clamp(20px, 5vw, 60px)', maxWidth: '900px', margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: '60px', ...reveal('process') }}>
                    <span style={{ fontSize: '12px', color: '#f093fb', letterSpacing: '3px', fontWeight: '600', textTransform: 'uppercase' }}>Process</span>
                    <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: '800', color: '#f0f0f5', margin: '12px 0 0 0', letterSpacing: '-1px' }}>
                        From document to insight <br />
                        <span style={{ background: 'linear-gradient(135deg, #f093fb, #f5576c)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>in three steps</span>
                    </h2>
                </div>

                {[
                    { n: '01', title: 'Upload Your PDF', desc: 'Drop any document — research papers, textbooks, legal contracts. Our engine reads every page intelligently.', color: '#667eea' },
                    { n: '02', title: 'AI Extracts Knowledge', desc: 'NVIDIA Nemotron identifies 25-50+ entities, maps relationships, and builds multi-level hierarchies automatically.', color: '#f093fb' },
                    { n: '03', title: 'Explore & Discover', desc: 'Navigate your knowledge in immersive 3D. Chat with AI about connections. Export insights for your work.', color: '#00d2ff' },
                ].map((item, i) => (
                    <div key={i} id={`step-${i}`} data-reveal style={{
                        display: 'flex', gap: '28px', alignItems: 'flex-start', marginBottom: '24px',
                        padding: '28px 30px', borderRadius: '18px', border: '1px solid transparent',
                        transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                        ...reveal(`step-${i}`, i * 0.15),
                    }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}
                    >
                        <div style={{
                            minWidth: '52px', height: '52px', borderRadius: '14px',
                            background: `linear-gradient(135deg, ${item.color}15, ${item.color}08)`,
                            border: `1px solid ${item.color}20`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '16px', fontWeight: '800', color: item.color,
                        }}>{item.n}</div>
                        <div>
                            <h3 style={{ fontSize: '19px', fontWeight: '700', color: '#e8e8ed', margin: '0 0 8px 0', letterSpacing: '-0.3px' }}>{item.title}</h3>
                            <p style={{ fontSize: '14.5px', color: 'rgba(255,255,255,0.35)', lineHeight: 1.7, margin: 0 }}>{item.desc}</p>
                        </div>
                    </div>
                ))}
            </section>

            {/* CTA */}
            <section id="about" data-reveal style={{ position: 'relative', zIndex: 10, padding: '80px clamp(20px, 5vw, 60px) 120px', maxWidth: '800px', margin: '0 auto' }}>
                <div style={{
                    padding: '70px 50px', textAlign: 'center', borderRadius: '28px', position: 'relative', overflow: 'hidden',
                    background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                    backdropFilter: 'blur(20px)',
                    ...reveal('about'),
                }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'linear-gradient(135deg, rgba(102,126,234,0.06) 0%, rgba(118,75,162,0.04) 50%, rgba(240,147,251,0.03) 100%)', pointerEvents: 'none' }} />
                    <h2 style={{ fontSize: 'clamp(26px, 3.5vw, 38px)', fontWeight: '800', color: '#f0f0f5', margin: '0 0 14px 0', position: 'relative', letterSpacing: '-0.8px' }}>
                        Ready to map your knowledge?
                    </h2>
                    <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.35)', margin: '0 0 36px 0', position: 'relative' }}>
                        Start exploring the hidden connections in your documents today.
                    </p>
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', color: '#fff',
                        padding: '17px 44px', borderRadius: '14px', fontWeight: '700', fontSize: '15px', cursor: 'pointer',
                        boxShadow: '0 4px 30px rgba(102, 126, 234, 0.3)', position: 'relative',
                        transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'translateY(-3px)'; e.target.style.boxShadow = '0 8px 40px rgba(102, 126, 234, 0.45)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 4px 30px rgba(102, 126, 234, 0.3)'; }}
                    >Launch GraphMind →</button>
                </div>
            </section>

            {/* Creator Section */}
            <section id="creator" data-reveal style={{ position: 'relative', zIndex: 10, padding: '60px clamp(20px, 5vw, 60px) 40px', maxWidth: '700px', margin: '0 auto' }}>
                <div style={{
                    padding: '44px 40px', borderRadius: '24px', position: 'relative', overflow: 'hidden',
                    background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                    backdropFilter: 'blur(20px)', display: 'flex', alignItems: 'center', gap: '30px',
                    ...reveal('creator'),
                }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'linear-gradient(135deg, rgba(102,126,234,0.04) 0%, rgba(240,147,251,0.03) 100%)', pointerEvents: 'none' }} />

                    {/* Avatar */}
                    <div style={{
                        minWidth: '80px', height: '80px', borderRadius: '50%',
                        background: 'linear-gradient(135deg, #667eea, #764ba2, #f093fb)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '32px', fontWeight: '800', color: '#fff', position: 'relative',
                        boxShadow: '0 4px 20px rgba(102, 126, 234, 0.25)',
                    }}>
                        PR
                    </div>

                    <div style={{ position: 'relative', flex: 1 }}>
                        <div style={{ fontSize: '11px', color: '#667eea', letterSpacing: '2.5px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '6px' }}>Creator</div>
                        <h3 style={{ fontSize: '22px', fontWeight: '800', color: '#f0f0f5', margin: '0 0 6px 0', letterSpacing: '-0.5px' }}>Toganti Pruthvi Raj</h3>
                        <p style={{ fontSize: '13.5px', color: 'rgba(255,255,255,0.35)', margin: '0 0 16px 0', lineHeight: 1.5 }}>
                            Developer & AI Enthusiast · Building intelligent tools for the modern web.
                        </p>

                        {/* Social Links */}
                        <div style={{ display: 'flex', gap: '10px' }}>
                            {[
                                {
                                    label: 'GitHub', href: 'https://github.com/prutxvi', icon: (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" /></svg>
                                    )
                                },
                                {
                                    label: 'LinkedIn', href: 'https://www.linkedin.com/in/pruthvi-raj-586263284/', icon: (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" /></svg>
                                    )
                                },
                                {
                                    label: 'Instagram', href: 'https://www.instagram.com/pruthvi.talks/', icon: (
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" /></svg>
                                    )
                                },
                            ].map((s, i) => (
                                <a key={i} href={s.href} target="_blank" rel="noreferrer" style={{
                                    width: '38px', height: '38px', borderRadius: '10px',
                                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    color: 'rgba(255,255,255,0.4)', transition: 'all 0.3s', textDecoration: 'none',
                                }}
                                    onMouseEnter={e => { e.currentTarget.style.borderColor = '#667eea'; e.currentTarget.style.color = '#667eea'; e.currentTarget.style.background = 'rgba(102,126,234,0.08)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                                    title={s.label}
                                >{s.icon}</a>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer style={{ position: 'relative', zIndex: 10, padding: '30px 50px', borderTop: '1px solid rgba(255,255,255,0.04)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.15)', margin: 0 }}>
                    © 2025 GraphMind · Built by <span style={{ color: 'rgba(255,255,255,0.3)' }}>Toganti Pruthvi Raj</span>
                </p>
                <div style={{ display: 'flex', gap: '20px' }}>
                    {[
                        { label: 'GitHub', href: 'https://github.com/prutxvi' },
                        { label: 'LinkedIn', href: 'https://www.linkedin.com/in/pruthvi-raj-586263284/' },
                        { label: 'Instagram', href: 'https://www.instagram.com/pruthvi.talks/' },
                    ].map((l, i) => (
                        <a key={i} href={l.href} target="_blank" rel="noreferrer" style={{
                            fontSize: '12.5px', color: 'rgba(255,255,255,0.2)', textDecoration: 'none', transition: 'color 0.3s',
                        }}
                            onMouseEnter={e => e.target.style.color = '#667eea'}
                            onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.2)'}
                        >{l.label}</a>
                    ))}
                </div>
            </footer>

            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
        @keyframes cursorBlink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body { background: #09090f; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(102,126,234,0.4); }
        @media (max-width: 768px) {
          nav > div:last-child > a { display: none !important; }
        }
      `}</style>
        </div>
    );
}

export default LandingPage;
