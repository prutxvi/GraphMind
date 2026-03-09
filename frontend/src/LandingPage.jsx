import { useState, useEffect, useRef, useCallback } from 'react';

function LandingPage({ onEnter }) {
    const canvasRef = useRef(null);
    const [typedText, setTypedText] = useState('');
    const [showContent, setShowContent] = useState(false);
    const [isExiting, setIsExiting] = useState(false);
    const fullText = 'Transform Documents into Living Knowledge';

    // Typing animation
    useEffect(() => {
        setTimeout(() => setShowContent(true), 300);
        let i = 0;
        const timer = setInterval(() => {
            if (i <= fullText.length) {
                setTypedText(fullText.slice(0, i));
                i++;
            } else {
                clearInterval(timer);
            }
        }, 45);
        return () => clearInterval(timer);
    }, []);

    // Neural network particle canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let animationId;
        let mouse = { x: -1000, y: -1000 };

        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        resize();
        window.addEventListener('resize', resize);

        const handleMouseMove = (e) => {
            mouse.x = e.clientX;
            mouse.y = e.clientY;
        };
        window.addEventListener('mousemove', handleMouseMove);

        // Create particles
        const particles = [];
        const particleCount = 80;
        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                radius: Math.random() * 2.5 + 1,
                color: ['#00ff88', '#00aaff', '#aa00ff', '#ff0088'][Math.floor(Math.random() * 4)],
                alpha: Math.random() * 0.6 + 0.2,
                pulseSpeed: Math.random() * 0.02 + 0.01,
                pulsePhase: Math.random() * Math.PI * 2,
            });
        }

        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Update & draw particles
            particles.forEach((p, i) => {
                // Mouse repulsion
                const dx = p.x - mouse.x;
                const dy = p.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    const force = (150 - dist) / 150;
                    p.vx += (dx / dist) * force * 0.3;
                    p.vy += (dy / dist) * force * 0.3;
                }

                p.x += p.vx;
                p.y += p.vy;
                p.vx *= 0.99;
                p.vy *= 0.99;

                // Bounce
                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
                p.x = Math.max(0, Math.min(canvas.width, p.x));
                p.y = Math.max(0, Math.min(canvas.height, p.y));

                // Pulse
                const pulse = Math.sin(Date.now() * p.pulseSpeed + p.pulsePhase) * 0.3 + 0.7;

                // Draw particle glow
                const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 4);
                gradient.addColorStop(0, p.color + Math.floor(p.alpha * pulse * 180).toString(16).padStart(2, '0'));
                gradient.addColorStop(1, p.color + '00');
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius * 4, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();

                // Draw particle core
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius * pulse, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = p.alpha * pulse;
                ctx.fill();
                ctx.globalAlpha = 1;

                // Draw connections
                particles.forEach((p2, j) => {
                    if (j <= i) return;
                    const ddx = p.x - p2.x;
                    const ddy = p.y - p2.y;
                    const ddist = Math.sqrt(ddx * ddx + ddy * ddy);
                    if (ddist < 180) {
                        const opacity = (1 - ddist / 180) * 0.15;
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.strokeStyle = `rgba(0, 255, 136, ${opacity})`;
                        ctx.lineWidth = 0.5;
                        ctx.stroke();
                    }
                });
            });

            animationId = requestAnimationFrame(animate);
        };
        animate();

        return () => {
            cancelAnimationFrame(animationId);
            window.removeEventListener('resize', resize);
            window.removeEventListener('mousemove', handleMouseMove);
        };
    }, []);

    const handleEnter = useCallback(() => {
        setIsExiting(true);
        setTimeout(() => onEnter(), 800);
    }, [onEnter]);

    const features = [
        { icon: '📄', title: 'PDF Intelligence', desc: 'Upload any document and watch AI extract complex relationships automatically', color: '#00ff88' },
        { icon: '🌐', title: '3D Visualization', desc: 'Explore interactive 3D knowledge graphs powered by Three.js and WebGL', color: '#00aaff' },
        { icon: '🤖', title: 'AI Chat', desc: 'Ask questions about your graph with context-aware neural responses', color: '#aa00ff' },
        { icon: '🧠', title: 'Deep Analysis', desc: 'AI-powered analytics with hub detection, clustering, and insights', color: '#ff0088' },
    ];

    const stats = [
        { value: '50+', label: 'Nodes per PDF' },
        { value: '3D', label: 'Visualization' },
        { value: 'AI', label: 'Powered' },
        { value: '∞', label: 'Possibilities' },
    ];

    return (
        <div style={{
            width: '100vw', minHeight: '100vh', background: '#030308', position: 'relative',
            overflow: isExiting ? 'hidden' : 'auto',
            fontFamily: "'Inter', 'Segoe UI', sans-serif",
            transition: 'opacity 0.8s, transform 0.8s',
            opacity: isExiting ? 0 : 1,
            transform: isExiting ? 'scale(1.05)' : 'scale(1)',
        }}>
            <canvas ref={canvasRef} style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }} />

            {/* Gradient overlays */}
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'radial-gradient(ellipse at 20% 50%, rgba(0, 255, 136, 0.06) 0%, transparent 60%)', zIndex: 1, pointerEvents: 'none' }} />
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'radial-gradient(ellipse at 80% 20%, rgba(170, 0, 255, 0.05) 0%, transparent 60%)', zIndex: 1, pointerEvents: 'none' }} />

            {/* Navbar */}
            <nav style={{
                position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
                padding: '20px 50px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'rgba(3, 3, 8, 0.6)', backdropFilter: 'blur(20px)',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(-20px)',
                transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
            }}>
                <div style={{ fontSize: '24px', fontWeight: '900', color: 'white', letterSpacing: '-0.5px' }}>
                    GRAPH<span style={{ color: '#00ff88', textShadow: '0 0 20px rgba(0,255,136,0.5)' }}>MIND</span>
                </div>
                <div style={{ display: 'flex', gap: '35px', alignItems: 'center' }}>
                    <a href="#features" style={{ color: '#888', textDecoration: 'none', fontSize: '14px', fontWeight: '500', transition: 'color 0.3s' }}
                        onMouseEnter={e => e.target.style.color = '#fff'}
                        onMouseLeave={e => e.target.style.color = '#888'}>Features</a>
                    <a href="#how" style={{ color: '#888', textDecoration: 'none', fontSize: '14px', fontWeight: '500', transition: 'color 0.3s' }}
                        onMouseEnter={e => e.target.style.color = '#fff'}
                        onMouseLeave={e => e.target.style.color = '#888'}>How It Works</a>
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #00ff88, #00cc6a)',
                        border: 'none', color: '#000', padding: '10px 24px', borderRadius: '25px',
                        fontWeight: '700', fontSize: '13px', cursor: 'pointer', letterSpacing: '0.5px',
                        boxShadow: '0 0 25px rgba(0,255,136,0.3)',
                        transition: 'all 0.3s',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'scale(1.05)'; e.target.style.boxShadow = '0 0 40px rgba(0,255,136,0.5)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'scale(1)'; e.target.style.boxShadow = '0 0 25px rgba(0,255,136,0.3)'; }}
                    >LAUNCH APP →</button>
                </div>
            </nav>

            {/* Hero Section */}
            <section style={{
                position: 'relative', zIndex: 10, minHeight: '100vh',
                display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
                textAlign: 'center', padding: '0 20px',
            }}>
                <div style={{
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(40px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
                }}>
                    <div style={{
                        display: 'inline-block', padding: '8px 20px', borderRadius: '50px',
                        border: '1px solid rgba(0, 255, 136, 0.3)', background: 'rgba(0, 255, 136, 0.05)',
                        fontSize: '12px', color: '#00ff88', fontWeight: '600', letterSpacing: '2px',
                        marginBottom: '30px',
                    }}>
                        ⚡ AI-POWERED KNOWLEDGE GRAPH ENGINE
                    </div>
                </div>

                <h1 style={{
                    fontSize: 'clamp(36px, 5vw, 72px)', fontWeight: '900', color: 'white',
                    lineHeight: 1.1, maxWidth: '900px', margin: '0 0 25px 0',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(40px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.5s',
                }}>
                    {typedText}
                    <span style={{ color: '#00ff88', animation: 'blink 1s infinite', fontWeight: '200' }}>|</span>
                </h1>

                <p style={{
                    fontSize: 'clamp(16px, 2vw, 20px)', color: '#888', maxWidth: '600px', lineHeight: 1.7,
                    margin: '0 0 50px 0',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(40px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.7s',
                }}>
                    Upload PDFs. Extract entities. Visualize connections in immersive 3D.
                    Powered by <span style={{ color: '#aa00ff' }}>NVIDIA Nemotron AI</span>.
                </p>

                <div style={{
                    display: 'flex', gap: '20px', flexWrap: 'wrap', justifyContent: 'center',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(40px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 0.9s',
                }}>
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #00ff88, #00cc6a)',
                        border: 'none', color: '#000', padding: '18px 45px', borderRadius: '50px',
                        fontWeight: '800', fontSize: '16px', cursor: 'pointer', letterSpacing: '1px',
                        boxShadow: '0 0 40px rgba(0,255,136,0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
                        transition: 'all 0.3s',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'translateY(-3px) scale(1.03)'; e.target.style.boxShadow = '0 10px 50px rgba(0,255,136,0.4)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'translateY(0) scale(1)'; e.target.style.boxShadow = '0 0 40px rgba(0,255,136,0.3)'; }}
                    >
                        🚀 ENTER GRAPHMIND
                    </button>
                    <a href="https://github.com/sricharanreddynyayam-crypto/GraphMind" target="_blank" rel="noreferrer" style={{
                        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
                        color: '#ccc', padding: '18px 35px', borderRadius: '50px',
                        fontWeight: '600', fontSize: '15px', cursor: 'pointer', textDecoration: 'none',
                        transition: 'all 0.3s', display: 'inline-flex', alignItems: 'center', gap: '8px',
                    }}
                        onMouseEnter={e => { e.target.style.borderColor = '#00ff88'; e.target.style.color = '#fff'; }}
                        onMouseLeave={e => { e.target.style.borderColor = 'rgba(255,255,255,0.15)'; e.target.style.color = '#ccc'; }}
                    >
                        ⭐ GitHub
                    </a>
                </div>

                {/* Stats row */}
                <div style={{
                    display: 'flex', gap: '50px', marginTop: '80px', flexWrap: 'wrap', justifyContent: 'center',
                    opacity: showContent ? 1 : 0, transform: showContent ? 'translateY(0)' : 'translateY(30px)',
                    transition: 'all 1s cubic-bezier(0.16, 1, 0.3, 1) 1.2s',
                }}>
                    {stats.map((s, i) => (
                        <div key={i} style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '32px', fontWeight: '900', color: '#00ff88', textShadow: '0 0 15px rgba(0,255,136,0.3)' }}>{s.value}</div>
                            <div style={{ fontSize: '12px', color: '#666', letterSpacing: '2px', marginTop: '4px' }}>{s.label}</div>
                        </div>
                    ))}
                </div>

                {/* Scroll indicator */}
                <div style={{
                    position: 'absolute', bottom: 40, left: '50%', transform: 'translateX(-50%)',
                    animation: 'bounce 2s infinite', opacity: 0.4,
                }}>
                    <div style={{ width: '24px', height: '40px', border: '2px solid #666', borderRadius: '12px', position: 'relative' }}>
                        <div style={{ width: '4px', height: '8px', background: '#00ff88', borderRadius: '2px', position: 'absolute', top: '8px', left: '50%', transform: 'translateX(-50%)', animation: 'scrollDot 2s infinite' }} />
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" style={{ position: 'relative', zIndex: 10, padding: '120px 50px', maxWidth: '1200px', margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: '70px' }}>
                    <div style={{ fontSize: '12px', color: '#00ff88', letterSpacing: '3px', fontWeight: '600', marginBottom: '15px' }}>CAPABILITIES</div>
                    <h2 style={{ fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: '900', color: 'white', margin: 0 }}>
                        The Future of <span style={{ background: 'linear-gradient(135deg, #00ff88, #00aaff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Knowledge Discovery</span>
                    </h2>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '24px' }}>
                    {features.map((f, i) => (
                        <div key={i} style={{
                            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                            borderRadius: '20px', padding: '40px 30px', cursor: 'default',
                            transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                            position: 'relative', overflow: 'hidden',
                        }}
                            onMouseEnter={e => {
                                e.currentTarget.style.transform = 'translateY(-8px)';
                                e.currentTarget.style.borderColor = f.color + '40';
                                e.currentTarget.style.boxShadow = `0 20px 60px ${f.color}15`;
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                                e.currentTarget.style.boxShadow = 'none';
                            }}
                        >
                            <div style={{
                                position: 'absolute', top: '-30px', right: '-30px', width: '100px', height: '100px',
                                background: `radial-gradient(circle, ${f.color}10 0%, transparent 70%)`,
                            }} />
                            <div style={{ fontSize: '40px', marginBottom: '20px' }}>{f.icon}</div>
                            <h3 style={{ fontSize: '20px', fontWeight: '800', color: 'white', margin: '0 0 12px 0' }}>{f.title}</h3>
                            <p style={{ fontSize: '14px', color: '#888', lineHeight: 1.7, margin: 0 }}>{f.desc}</p>
                            <div style={{ height: '3px', width: '40px', background: f.color, borderRadius: '2px', marginTop: '20px', opacity: 0.6 }} />
                        </div>
                    ))}
                </div>
            </section>

            {/* How It Works */}
            <section id="how" style={{ position: 'relative', zIndex: 10, padding: '120px 50px', maxWidth: '900px', margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: '70px' }}>
                    <div style={{ fontSize: '12px', color: '#aa00ff', letterSpacing: '3px', fontWeight: '600', marginBottom: '15px' }}>WORKFLOW</div>
                    <h2 style={{ fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: '900', color: 'white', margin: 0 }}>
                        Three Steps to <span style={{ background: 'linear-gradient(135deg, #aa00ff, #ff0088)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Clarity</span>
                    </h2>
                </div>

                {[
                    { step: '01', title: 'Upload Your Document', desc: 'Drop any PDF — research papers, textbooks, reports. Our engine reads every page.', color: '#00ff88' },
                    { step: '02', title: 'AI Extracts Knowledge', desc: 'NVIDIA Nemotron AI identifies 25-50+ entities, relationships, and hierarchies automatically.', color: '#00aaff' },
                    { step: '03', title: 'Explore in 3D', desc: 'Navigate your knowledge graph in immersive 3D. Chat with AI. Discover hidden connections.', color: '#aa00ff' },
                ].map((item, i) => (
                    <div key={i} style={{
                        display: 'flex', gap: '30px', alignItems: 'flex-start', marginBottom: '50px',
                        padding: '30px', borderRadius: '16px',
                        transition: 'all 0.3s',
                    }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                        <div style={{
                            fontSize: '48px', fontWeight: '900', color: item.color, opacity: 0.2,
                            minWidth: '80px', textAlign: 'center', lineHeight: 1,
                        }}>{item.step}</div>
                        <div>
                            <h3 style={{ fontSize: '22px', fontWeight: '800', color: 'white', margin: '0 0 10px 0' }}>{item.title}</h3>
                            <p style={{ fontSize: '15px', color: '#888', lineHeight: 1.7, margin: 0 }}>{item.desc}</p>
                        </div>
                    </div>
                ))}
            </section>

            {/* CTA Section */}
            <section style={{
                position: 'relative', zIndex: 10, padding: '120px 50px', textAlign: 'center',
            }}>
                <div style={{
                    maxWidth: '700px', margin: '0 auto', padding: '80px 50px',
                    background: 'linear-gradient(135deg, rgba(0,255,136,0.05), rgba(170,0,255,0.05))',
                    border: '1px solid rgba(0,255,136,0.15)',
                    borderRadius: '30px', position: 'relative', overflow: 'hidden',
                }}>
                    <div style={{
                        position: 'absolute', top: '-50%', left: '-50%', width: '200%', height: '200%',
                        background: 'radial-gradient(circle at 30% 50%, rgba(0,255,136,0.08) 0%, transparent 50%)',
                        pointerEvents: 'none',
                    }} />
                    <h2 style={{ fontSize: '36px', fontWeight: '900', color: 'white', margin: '0 0 15px 0', position: 'relative' }}>
                        Ready to Map Your Knowledge?
                    </h2>
                    <p style={{ fontSize: '16px', color: '#888', margin: '0 0 40px 0', position: 'relative' }}>
                        Start exploring the connections hiding in your documents.
                    </p>
                    <button onClick={handleEnter} style={{
                        background: 'linear-gradient(135deg, #00ff88, #00cc6a)',
                        border: 'none', color: '#000', padding: '20px 50px', borderRadius: '50px',
                        fontWeight: '800', fontSize: '17px', cursor: 'pointer', letterSpacing: '1px',
                        boxShadow: '0 0 50px rgba(0,255,136,0.3)', position: 'relative',
                        transition: 'all 0.3s',
                    }}
                        onMouseEnter={e => { e.target.style.transform = 'translateY(-3px)'; e.target.style.boxShadow = '0 15px 60px rgba(0,255,136,0.4)'; }}
                        onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 0 50px rgba(0,255,136,0.3)'; }}
                    >
                        🚀 LAUNCH GRAPHMIND
                    </button>
                </div>
            </section>

            {/* Footer */}
            <footer style={{
                position: 'relative', zIndex: 10, padding: '40px 50px',
                borderTop: '1px solid rgba(255,255,255,0.05)', textAlign: 'center',
            }}>
                <div style={{ fontSize: '14px', color: '#444' }}>
                    Built with ❤️ using <span style={{ color: '#666' }}>React</span> · <span style={{ color: '#666' }}>FastAPI</span> · <span style={{ color: '#666' }}>Three.js</span> · <span style={{ color: '#666' }}>NVIDIA AI</span>
                </div>
            </footer>

            {/* Global animations */}
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
        @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
        @keyframes bounce { 0%, 100% { transform: translateX(-50%) translateY(0); } 50% { transform: translateX(-50%) translateY(10px); } }
        @keyframes scrollDot { 0% { top: 8px; opacity: 1; } 100% { top: 24px; opacity: 0; } }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #222; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #00ff88; }
      `}</style>
        </div>
    );
}

export default LandingPage;
