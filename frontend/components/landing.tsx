import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import { 
  ArrowRight, 
  ArrowUpRight, 
  Menu, 
  X, 
  MonitorSmartphone, 
  Code, 
  Globe, 
  Palette 
} from 'lucide-react';
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { useRouter } from 'next/navigation';

// --- Utilities ---
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Shaders ---
const VERTEX_SHADER = `
  #define PI 3.141592653589793
  #define PI2 6.283185307179586
  #define PHI 1.618033988749

  attribute float aIndex;
  attribute float aSize;
  attribute float aPhase;

  uniform float uCount;
  uniform float uFormA;
  uniform float uFormB;
  uniform float uMix;
  uniform float uTime;
  uniform vec3 uMouse;
  uniform float uMouseRadius;
  uniform float uPointSize;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform float uScrollVel;

  varying vec3 vColor;
  varying float vAlpha;

  float hash(float n) { return fract(sin(n + 0.1) * 43758.5453); }

  vec3 formSphere(float i, float n) {
      float p = acos(1.0 - 2.0 * (i + 0.5) / n);
      float t = PI2 * PHI * i;
      float r = 2.8 + hash(i * 6.7) * 0.4;
      return r * vec3(sin(p)*cos(t), sin(p)*sin(t), cos(p));
  }
  vec3 formHelix(float i, float n) {
      float t = i / n * PI2 * 4.0;
      float s = floor(mod(i, 3.0));
      float r = 1.2 + hash(i * 3.1) * 0.3;
      return vec3(r * cos(t + s * PI2 / 3.0), (i/n - 0.5) * 7.0, r * sin(t + s * PI2 / 3.0));
  }
  vec3 formGrid(float i, float n) {
      float side = ceil(sqrt(n));
      float x = (mod(i, side) / side - 0.5) * 7.0;
      float z = (floor(i / side) / side - 0.5) * 7.0;
      return vec3(x, sin(x * 1.2 + z * 0.8) * cos(z) * 0.6, z);
  }
  vec3 formTorus(float i, float n) {
      float t = i / n * PI2;
      float R = 2.2, r = 0.8 + hash(i * 2.9) * 0.2;
      return vec3((R + r * cos(3.0*t)) * cos(2.0*t), (R + r * cos(3.0*t)) * sin(2.0*t), r * sin(3.0*t));
  }
  vec3 formGalaxy(float i, float n) {
      float arm = floor(mod(i, 4.0));
      float t = i / n;
      float r = pow(t, 0.5) * 3.5;
      float a = t * 12.0 + arm * PI2 / 4.0;
      float sc = hash(i * 5.1) * 0.4;
      return vec3(r*cos(a)+(hash(i*2.3)-0.5)*sc, (hash(i*8.7)-0.5)*0.3, r*sin(a)+(hash(i*4.1)-0.5)*sc);
  }
  vec3 formVortex(float i, float n) {
      float t = i / n;
      float a = t * PI2 * 8.0;
      float r = (1.0 - t) * 3.5;
      return vec3(r * cos(a), (t - 0.5) * 5.0, r * sin(a));
  }
  vec3 getForm(float id, float i, float n) {
      if (id < 0.5) return formSphere(i, n);
      if (id < 1.5) return formHelix(i, n);
      if (id < 2.5) return formGrid(i, n);
      if (id < 3.5) return formTorus(i, n);
      if (id < 4.5) return formGalaxy(i, n);
      return formVortex(i, n);
  }

  void main() {
      vec3 posA = getForm(uFormA, aIndex, uCount);
      vec3 posB = getForm(uFormB, aIndex, uCount);
      float t = uMix * uMix * (3.0 - 2.0 * uMix);
      vec3 pos = mix(posA, posB, t);

      pos += vec3(sin(uTime*0.5+aPhase*PI2)*0.1, cos(uTime*0.4+aPhase*4.17)*0.1, sin(uTime*0.3+aPhase*5.03)*0.1);

      float vel = min(uScrollVel, 3.0);
      pos += vec3(sin(aPhase*20.0+uTime*2.0), cos(aPhase*15.0+uTime*1.5), sin(aPhase*25.0+uTime*1.8)) * vel * 0.06;

      vec3 diff = pos - uMouse;
      float dist = length(diff);
      if (dist < uMouseRadius && dist > 0.001) {
          float f = 1.0 - dist / uMouseRadius;
          pos += normalize(diff) * f * f * f * 1.0;
      }

      vColor = mix(uColorA, uColorB, t) * (0.7 + hash(aIndex * 7.3) * 0.3);
      if (dist < uMouseRadius) vColor += (1.0 - dist/uMouseRadius) * 0.2;
      vAlpha = 0.28 + aSize * 0.14 + min(vel, 2.0) * 0.04;

      vec4 mv = modelViewMatrix * vec4(pos, 1.0);
      gl_PointSize = clamp(aSize * uPointSize * (80.0 / -mv.z), 0.8, 22.0);
      gl_Position = projectionMatrix * mv;
  }
`;

const FRAGMENT_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
      float d = length(gl_PointCoord - 0.5);
      if (d > 0.5) discard;
      float a = (1.0 - smoothstep(0.3, 0.5, d)) * vAlpha;
      gl_FragColor = vec4(vColor, a);
  }
`;

// --- Optimized Void Scene Class ---
class VoidScene {
  canvas: HTMLCanvasElement;
  N: number;
  scroll: number = 0;
  scrollVel: number = 0;
  mouseNDC: { x: number; y: number } = { x: -100, y: -100 };
  mouse3D: THREE.Vector3;
  targetZ: number = 7;
  ren: THREE.WebGLRenderer;
  cam: THREE.PerspectiveCamera;
  scene: THREE.Scene;
  mat: THREE.ShaderMaterial;
  points: THREE.Points;
  _v: THREE.Vector3;
  _d: THREE.Vector3;
  animationId: number = 0;

  kf = [
    { s: 0.00, f: 0, z: 7,   r: 0.78, g: 1.0,  b: 0.0  },
    { s: 0.07, f: 0, z: 7,   r: 0.78, g: 1.0,  b: 0.0  },
    { s: 0.19, f: 1, z: 9,   r: 0.0,  g: 1.0,  b: 0.64 },
    { s: 0.26, f: 1, z: 9,   r: 0.0,  g: 1.0,  b: 0.64 },
    { s: 0.38, f: 2, z: 8,   r: 0.94, g: 0.94, b: 0.96 },
    { s: 0.45, f: 2, z: 8,   r: 0.94, g: 0.94, b: 0.96 },
    { s: 0.57, f: 3, z: 7.5, r: 1.0,  g: 0.0,  b: 0.25 },
    { s: 0.64, f: 3, z: 7.5, r: 1.0,  g: 0.0,  b: 0.25 },
    { s: 0.76, f: 4, z: 10,  r: 1.0,  g: 0.75, b: 0.0  },
    { s: 0.83, f: 4, z: 10,  r: 1.0,  g: 0.75, b: 0.0  },
    { s: 0.95, f: 5, z: 6,   r: 0.78, g: 1.0,  b: 0.0  },
    { s: 1.00, f: 5, z: 6,   r: 0.78, g: 1.0,  b: 0.0  },
  ];

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.N = window.innerWidth < 769 ? 3000 : 6000;
    this.mouse3D = new THREE.Vector3(100, 100, 100);
    this._v = new THREE.Vector3();
    this._d = new THREE.Vector3();
    
    this.init();
    this.setupEventListeners();
    this.animate();
  }

  init() {
    // Renderer
    this.ren = new THREE.WebGLRenderer({ 
      canvas: this.canvas, 
      antialias: false, 
      alpha: true 
    });
    this.ren.setSize(window.innerWidth, window.innerHeight);
    this.ren.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.ren.setClearColor(0x060606, 1);

    // Camera
    this.cam = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    this.cam.position.set(0, 0, 7);

    // Scene
    this.scene = new THREE.Scene();

    // Particles
    const geo = new THREE.BufferGeometry();
    const idx = new Float32Array(this.N);
    const sizes = new Float32Array(this.N);
    const phases = new Float32Array(this.N);
    
    for (let i = 0; i < this.N; i++) {
      idx[i] = i;
      sizes[i] = 0.4 + Math.random() * 1.0;
      phases[i] = Math.random();
    }
    
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.N * 3), 3));
    geo.setAttribute('aIndex', new THREE.BufferAttribute(idx, 1));
    geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));

    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms: {
        uCount: { value: this.N },
        uFormA: { value: 0 },
        uFormB: { value: 0 },
        uMix: { value: 0 },
        uTime: { value: 0 },
        uMouse: { value: new THREE.Vector3(100, 100, 100) },
        uMouseRadius: { value: 5.0 },
        uPointSize: { value: 1.2 },
        uColorA: { value: new THREE.Color(0.78, 1.0, 0.0) },
        uColorB: { value: new THREE.Color(0.78, 1.0, 0.0) },
        uScrollVel: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.scene.add(this.points);
  }

  setupEventListeners() {
    const handleResize = () => {
      this.cam.aspect = window.innerWidth / window.innerHeight;
      this.cam.updateProjectionMatrix();
      this.ren.setSize(window.innerWidth, window.innerHeight);
    };

    const handleMouseMove = (e: MouseEvent) => {
      this.mouseNDC.x = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouseNDC.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!e.touches[0]) return;
      this.mouseNDC.x = (e.touches[0].clientX / window.innerWidth) * 2 - 1;
      this.mouseNDC.y = -(e.touches[0].clientY / window.innerHeight) * 2 + 1;
    };

    const handleTouchEnd = () => {
      this.mouseNDC.x = -100;
      this.mouseNDC.y = -100;
    };

    window.addEventListener('resize', handleResize, { passive: true });
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('touchmove', handleTouchMove, { passive: true });
    window.addEventListener('touchend', handleTouchEnd, { passive: true });
  }

  getState(s: number) {
    let i = 0;
    while (i < this.kf.length - 1 && this.kf[i + 1].s <= s) i++;
    const a = this.kf[i];
    const b = this.kf[Math.min(i + 1, this.kf.length - 1)];
    const range = b.s - a.s;
    const t = range > 0 ? Math.max(0, Math.min(1, (s - a.s) / range)) : 0;
    return {
      fA: a.f, fB: b.f, mix: a.f === b.f ? 0 : t,
      z: a.z + (b.z - a.z) * t,
      rA: a.r, gA: a.g, bA: a.b,
      rB: b.r, gB: b.g, bB: b.b,
    };
  }

  animate() {
    this.animationId = requestAnimationFrame(() => this.animate());
    const t = performance.now() * 0.001;
    const st = this.getState(this.scroll);
    const u = this.mat.uniforms;

    u.uFormA.value = st.fA;
    u.uFormB.value = st.fB;
    u.uMix.value = st.mix;
    u.uTime.value = t;
    u.uScrollVel.value += (Math.abs(this.scrollVel) - u.uScrollVel.value) * 0.1;
    u.uColorA.value.setRGB(st.rA, st.gA, st.bA);
    u.uColorB.value.setRGB(st.rB, st.gB, st.bB);

    // Unproject mouse to z=0 plane
    this._v.set(this.mouseNDC.x, this.mouseNDC.y, 0.5).unproject(this.cam);
    this._d.copy(this._v).sub(this.cam.position).normalize();
    const dist = -this.cam.position.z / this._d.z;
    this.mouse3D.copy(this.cam.position).addScaledVector(this._d, dist);
    u.uMouse.value.lerp(this.mouse3D, 0.05);

    // Camera parallax + zoom
    this.targetZ += (st.z - this.targetZ) * 0.04;
    const mx = Math.max(-1, Math.min(1, this.mouseNDC.x));
    const my = Math.max(-1, Math.min(1, this.mouseNDC.y));
    this.cam.position.x += (mx * 0.4 - this.cam.position.x) * 0.02;
    this.cam.position.y += (my * 0.25 - this.cam.position.y) * 0.02;
    this.cam.position.z += (this.targetZ - this.cam.position.z) * 0.04;
    this.cam.lookAt(0, 0, 0);

    this.ren.render(this.scene, this.cam);
  }

  dispose() {
    cancelAnimationFrame(this.animationId);
    this.ren.dispose();
  }
}

// --- Text Scramble Utility ---
function scrambleText(el: HTMLElement) {
  const original = el.dataset.orig || (el.dataset.orig = el.innerText || '');
  const chars = '!<>-_\\/[]{}—=+*^?#________';
  let iter = 0;
  
  if ((el as any)._si) clearInterval((el as any)._si);
  
  (el as any)._si = setInterval(() => {
    el.textContent = original.split('').map((c, i) =>
      i < iter ? original[i] : chars[Math.floor(Math.random() * chars.length)]
    ).join('');
    iter += 0.5;
    if (iter >= original.length) { 
      clearInterval((el as any)._si); 
      el.textContent = original; 
    }
  }, 30);
}

// --- Components ---

const VoidBackground: React.FC<{ scrollProgress: number; scrollVelocity: number }> = React.memo(({ 
  scrollProgress, 
  scrollVelocity 
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<VoidScene | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    
    sceneRef.current = new VoidScene(canvasRef.current);
    
    return () => {
      if (sceneRef.current) {
        sceneRef.current.dispose();
      }
    };
  }, []);

  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.scroll = scrollProgress;
      sceneRef.current.scrollVel = scrollVelocity;
    }
  }, [scrollProgress, scrollVelocity]);

  return (
    <div className="fixed inset-0 z-0 pointer-events-none">
      <canvas ref={canvasRef} className="block w-full h-full" />
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(6,6,6,0.45)_100%)]" />
    </div>
  );
});

VoidBackground.displayName = 'VoidBackground';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const router = useRouter();
  
  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 60);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <nav className={cn("fixed top-0 left-0 right-0 z-[100] flex items-center justify-between px-5 md:px-10 py-5 transition-all duration-400", isScrolled ? "bg-bg/70 backdrop-blur-xl" : "bg-transparent")}>
      <a href="#" className="font-display text-lg font-extrabold tracking-[0.15em]">CREDITIQ<span className="text-accent">.</span></a>
      <div className="hidden md:flex gap-8">
        {['About', 'Services', 'Work', 'Contact'].map((item) => (
          <a key={item} href={`#${item.toLowerCase()}`} className="text-[0.78rem] font-normal tracking-[0.06em] text-text-muted hover:text-white transition-colors relative group">
            {item}<span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-accent transition-all duration-300 group-hover:w-full" />
          </a>
        ))}
      </div>
      <button 
        onClick={() => router.push('/login')}
        className="hidden md:flex items-center gap-1.5 text-[0.72rem] font-medium tracking-[0.08em] text-accent hover:opacity-70 transition-opacity"
      >
        Get Started <ArrowRight size={14} />
      </button>
      <button className="md:hidden z-[102] text-white" onClick={() => setIsMenuOpen(!isMenuOpen)}>{isMenuOpen ? <X size={24} /> : <Menu size={24} />}</button>
      <div className={cn("fixed inset-0 z-[101] bg-bg/97 backdrop-blur-2xl flex flex-col items-center justify-center gap-8 transition-all duration-500 md:hidden", isMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none")}>
        {['About', 'Services', 'Work', 'Contact'].map((item) => (
          <a key={item} href={`#${item.toLowerCase()}`} className="text-2xl font-display font-bold text-white" onClick={() => setIsMenuOpen(false)}>{item}</a>
        ))}
        <button 
          onClick={() => router.push('/login')}
          className="text-2xl font-display font-bold text-accent"
        >
          Get Started
        </button>
      </div>
    </nav>
  );
};

const Hero = () => {
  const titleRef = useRef<HTMLHeadingElement>(null);
  const tagRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const actionsRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  
  useEffect(() => {
    const chars = titleRef.current?.querySelectorAll('.hero-char');
    if (!chars) return;
    const tl = gsap.timeline({ delay: 0.15 });
    tl.fromTo(chars, { y: 80, rotateX: 40, opacity: 0 }, { y: 0, rotateX: 0, opacity: 1, duration: 0.7, stagger: 0.06, ease: 'expo.out' });
    tl.fromTo(tagRef.current, { y: 15, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: 'power2.out' }, '-=0.35');
    tl.fromTo(subRef.current, { y: 15, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: 'power2.out' }, '-=0.3');
    tl.fromTo(actionsRef.current, { y: 15, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: 'power2.out' }, '-=0.2');
  }, []);

  return (
    <section className="h-screen flex flex-col justify-center items-center text-center px-5 md:px-10 relative z-10">
      <div className="flex flex-col items-center">
        <div ref={tagRef} className="text-[0.8rem] font-semibold tracking-[0.25em] uppercase text-accent mb-6 px-5 py-2 rounded-full bg-bg/50 backdrop-blur-md border border-accent/10 opacity-0">AI-Powered Credit Intelligence</div>
        <h1 ref={titleRef} className="font-display text-[clamp(5rem,18vw,14rem)] font-extrabold tracking-[0.06em] leading-[1.05] perspective-[600px] drop-shadow-[0_0_60px_rgba(200,255,0,0.15)]">
          {"CREDITIQ".split('').map((char, i) => (<span key={i} className="hero-char inline-block origin-bottom-center">{char}</span>))}
        </h1>
        <p ref={subRef} className="text-[clamp(1.15rem,2.5vw,1.5rem)] text-white max-w-[580px] mt-6 leading-[1.6] font-medium drop-shadow-[0_2px_16px_rgba(6,6,6,1)] opacity-0">Transform your credit analysis with advanced AI-driven insights and automated risk assessment</p>
        <div ref={actionsRef} className="flex flex-col sm:flex-row gap-4 mt-10 opacity-0 justify-center w-full sm:w-auto">
          <button 
            onClick={() => router.push('/login')}
            className="inline-flex items-center justify-center gap-2 font-display text-[0.82rem] font-semibold px-7 py-3.5 rounded-full bg-accent text-bg hover:shadow-[0_0_30px_rgba(200,255,0,0.35)] transition-all duration-400 tracking-[0.04em] hover:-translate-y-0.5"
          >
            Get Started <ArrowRight size={16} />
          </button>
          <a href="#about" className="inline-flex items-center justify-center gap-2 font-display text-[0.82rem] font-semibold px-7 py-3.5 rounded-full border border-white/20 text-white bg-bg/50 backdrop-blur-md hover:border-accent hover:text-accent transition-all duration-400 tracking-[0.04em]">Learn More</a>
        </div>
      </div>
    </section>
  );
};

const Manifesto = () => {
  const textRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!textRef.current) return;
    const words = textRef.current.querySelectorAll('.mword');
    gsap.set(words, { opacity: 0.12 });
    gsap.to(words, { opacity: 1, stagger: 0.04, scrollTrigger: { trigger: textRef.current, start: 'top 65%', end: 'bottom 40%', scrub: true } });
  }, []);
  const text = "CreditIQ revolutionizes credit assessment with cutting-edge AI technology. We analyze thousands of data points to provide accurate, real-time credit scores and risk assessments. Our platform helps financial institutions make smarter, faster lending decisions while reducing risk and increasing operational efficiency.";
  return (
    <section id="about" className="min-h-screen flex items-center justify-center py-20 md:py-32 relative z-10">
      <div className="max-w-[860px] px-6 md:px-12">
        <p ref={textRef} className="font-display text-[clamp(1.6rem,3.5vw,2.8rem)] font-medium leading-[1.45] tracking-[-0.01em]">
          {text.split(' ').map((word, i) => (<span key={i} className="mword inline-block mr-[0.3em]">{word}</span>))}
        </p>
      </div>
    </section>
  );
};

const CAPABILITIES = [
  { num: '01', icon: <MonitorSmartphone size={28} />, title: 'AI Credit Scoring', desc: 'Advanced machine learning algorithms analyze multiple data sources to generate accurate credit scores in real-time.' },
  { num: '02', icon: <Code size={28} />, title: 'Risk Assessment', desc: 'Comprehensive risk evaluation using predictive analytics and historical data patterns to minimize default rates.' },
  { num: '03', icon: <Globe size={28} />, title: 'Fraud Detection', desc: 'Sophisticated pattern recognition systems identify and prevent fraudulent activities before they impact your business.' },
  { num: '04', icon: <Palette size={28} />, title: 'Automated Reports', desc: 'Generate detailed credit reports and insights automatically, saving time and improving decision-making accuracy.' }
];

const CapCard: React.FC<{ cap: typeof CAPABILITIES[0], index: number }> = ({ cap }) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const scrambleText = (el: HTMLElement) => {
    const original = el.innerText;
    const chars = '!<>-_\\/[]{}—=+*^?#________';
    let iter = 0;
    const interval = setInterval(() => {
      el.innerText = original.split('').map((c, i) => i < iter ? original[i] : chars[Math.floor(Math.random() * chars.length)]).join('');
      iter += 0.5;
      if (iter >= original.length) { clearInterval(interval); el.innerText = original; }
    }, 30);
  };
  useEffect(() => {
    if (!cardRef.current) return;
    gsap.fromTo(cardRef.current, { y: 40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: cardRef.current, start: 'top 88%' } });
    const handleMouseMove = (e: MouseEvent) => {
      const r = cardRef.current!.getBoundingClientRect();
      cardRef.current!.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
      cardRef.current!.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
    };
    cardRef.current.addEventListener('mousemove', handleMouseMove);
    return () => cardRef.current?.removeEventListener('mousemove', handleMouseMove);
  }, []);
  return (
    <div ref={cardRef} onMouseEnter={() => titleRef.current && scrambleText(titleRef.current)} className="bg-glass border border-glass-border rounded-lg p-6 md:p-10 transition-all duration-400 hover:border-accent/30 hover:-translate-y-1 relative overflow-hidden group">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_var(--mx,50%)_var(--my,50%),rgba(200,255,0,0.05),transparent_60%)] opacity-0 group-hover:opacity-100 transition-opacity duration-400" />
      <span className="font-display text-[0.7rem] font-bold text-accent opacity-40 tracking-widest block mb-5">{cap.num}</span>
      <div className="text-accent mb-4 block">{cap.icon}</div>
      <h3 ref={titleRef} className="font-display text-lg font-bold mb-2.5 tracking-tight">{cap.title}</h3>
      <p className="text-[0.82rem] text-text-muted leading-relaxed font-light">{cap.desc}</p>
    </div>
  );
};

const Capabilities = () => {
  const headingRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!headingRef.current) return;
    gsap.to(headingRef.current, { y: 0, duration: 1, ease: 'expo.out', scrollTrigger: { trigger: headingRef.current.parentElement, start: 'top 85%' } });
  }, []);
  return (
    <section id="services" className="py-20 md:py-40 relative z-10">
      <div className="max-w-[1200px] mx-auto px-5 md:px-10">
        <div className="flex items-center gap-3 text-accent text-[0.68rem] font-medium tracking-[0.2em] uppercase mb-6"><div className="w-5 h-[1px] bg-accent shadow-[0_0_8px_var(--color-accent)]" />Features</div>
        <h2 className="heading-reveal"><span ref={headingRef} className="heading-reveal-inner font-display text-4xl md:text-6xl font-bold">Capabilities</span></h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-5 mt-12">{CAPABILITIES.map((cap, i) => (<CapCard key={cap.num} cap={cap} index={i} />))}</div>
      </div>
    </section>
  );
};

const METRICS = [
  { label: 'Credits Analyzed', count: 147 }, { label: 'Financial Institutions', count: 52 }, { label: 'Accuracy Rate', count: 98 }, { label: 'Years Experience', count: 9 }
];

const MetricItem: React.FC<{ metric: typeof METRICS[0], index: number }> = ({ metric, index }) => {
  const numRef = useRef<HTMLSpanElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!numRef.current || !containerRef.current) return;
    gsap.fromTo(numRef.current, { textContent: 0 }, { textContent: metric.count, duration: 2, ease: 'power2.out', snap: { textContent: 1 }, scrollTrigger: { trigger: numRef.current, start: 'top 85%' } });
    gsap.fromTo(containerRef.current, { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, delay: index * 0.1, ease: 'power2.out', scrollTrigger: { trigger: containerRef.current, start: 'top 90%' } });
  }, [metric.count, index]);
  return (
    <div ref={containerRef} className="text-center">
      <span ref={numRef} className="font-display text-[clamp(2.5rem,5vw,4rem)] font-extrabold block text-accent drop-shadow-[0_0_30px_rgba(200,255,0,0.2)]">0</span>
      <span className="text-[0.72rem] text-text-muted tracking-[0.08em] mt-1 block uppercase">{metric.label}</span>
    </div>
  );
};

const Metrics = () => {
  return (
    <section className="py-20 md:py-28 relative z-10">
      <div className="max-w-[1200px] mx-auto px-5 md:px-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">{METRICS.map((metric, i) => (<MetricItem key={metric.label} metric={metric} index={i} />))}</div>
      </div>
    </section>
  );
};

const CTA = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const router = useRouter();
  
  useEffect(() => {
    if (!containerRef.current) return;
    gsap.fromTo(titleRef.current, { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 1, ease: 'power2.out', scrollTrigger: { trigger: containerRef.current, start: 'top 70%' } });
    gsap.fromTo(subRef.current, { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: containerRef.current, start: 'top 65%' } });
    gsap.fromTo(btnRef.current, { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: containerRef.current, start: 'top 60%' } });
    const handleMouseMove = (e: MouseEvent) => {
      if (!btnRef.current) return;
      const r = btnRef.current.getBoundingClientRect();
      const x = e.clientX - r.left - r.width / 2;
      const y = e.clientY - r.top - r.height / 2;
      gsap.to(btnRef.current, { x: x * 0.3, y: y * 0.3, duration: 0.4, ease: 'power2.out' });
    };
    const handleMouseLeave = () => {
      if (!btnRef.current) return;
      gsap.to(btnRef.current, { x: 0, y: 0, duration: 0.7, ease: 'elastic.out(1, 0.3)' });
    };
    btnRef.current?.addEventListener('mousemove', handleMouseMove);
    btnRef.current?.addEventListener('mouseleave', handleMouseLeave);
    return () => { btnRef.current?.removeEventListener('mousemove', handleMouseMove); btnRef.current?.removeEventListener('mouseleave', handleMouseLeave); };
  }, []);
  return (
    <section id="contact" ref={containerRef} className="min-h-[80vh] flex items-center justify-center text-center py-20 md:py-40 px-5 relative z-10">
      <div className="max-w-[800px]">
        <div className="flex items-center justify-center gap-3 text-accent text-[0.68rem] font-medium tracking-[0.2em] uppercase mb-6"><div className="w-5 h-[1px] bg-accent shadow-[0_0_8px_var(--color-accent)]" />Get Started</div>
        <h2 ref={titleRef} className="font-display text-[clamp(2.2rem,5.5vw,4.5rem)] font-extrabold leading-[1.15] tracking-tight drop-shadow-[0_0_60px_rgba(200,255,0,0.1)]">Transform your<br />credit analysis with <em className="italic text-accent not-italic">AI-powered insights</em></h2>
        <p ref={subRef} className="text-[0.95rem] text-text-muted mt-5 font-light">Ready to revolutionize your credit assessment process?</p>
        <button 
          ref={btnRef}
          onClick={() => router.push('/login')}
          className="inline-flex items-center gap-2.5 mt-10 px-8 py-3.5 border border-accent text-accent rounded-full text-[0.82rem] font-medium tracking-[0.06em] transition-all duration-400 hover:bg-accent hover:text-bg hover:shadow-[0_0_30px_rgba(200,255,0,0.3)] will-change-transform"
        >
          <span>Start Free Trial</span><ArrowRight size={18} />
        </button>
      </div>
    </section>
  );
};

const Footer = () => {
  const innerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!innerRef.current) return;
    gsap.fromTo(innerRef.current, { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: innerRef.current, start: 'top 95%' } });
  }, []);
  return (
    <footer className="relative z-10 bg-bg-alt border-top border-glass-border pt-12 pb-6">
      <div ref={innerRef} className="max-w-[1200px] mx-auto px-5 md:px-10 flex flex-col md:flex-row justify-between items-start gap-8">
        <div className="flex flex-col"><span className="font-display text-lg font-extrabold tracking-[0.15em]">CREDITIQ<span className="text-accent">.</span></span><p className="text-[0.75rem] text-text-dim mt-1">AI-Powered Credit Intelligence</p></div>
        <div className="flex gap-16 md:gap-20">
          <div className="flex flex-col gap-2"><span className="text-[0.65rem] font-semibold tracking-[0.15em] uppercase text-text-muted mb-1">Navigation</span>{['Services', 'About', 'Contact'].map(item => (<a key={item} href={`#${item.toLowerCase()}`} className="text-[0.78rem] text-text-dim hover:text-accent transition-colors">{item}</a>))}</div>
          <div className="flex flex-col gap-2"><span className="text-[0.65rem] font-semibold tracking-[0.15em] uppercase text-text-muted mb-1">Company</span>{['Privacy', 'Terms', 'Support'].map(item => (<a key={item} href="#" className="text-[0.78rem] text-text-dim hover:text-accent transition-colors">{item}</a>))}</div>
        </div>
      </div>
      <div className="max-w-[1200px] mx-auto px-5 md:px-10 flex flex-col md:flex-row justify-between mt-10 pt-5 border-t border-glass-border text-[0.68rem] text-text-dim"><span>© 2025 CreditIQ</span><span className="mt-1 md:mt-0">Powered by Advanced AI</span></div>
    </footer>
  );
};

// --- Main App ---

export default function LandingPage() {
  const [scrollProgress, setScrollProgress] = useState(0);
  const [scrollVelocity, setScrollVelocity] = useState(0);

  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.12, wheelMultiplier: 1.0, smoothWheel: true });
    lenis.on('scroll', (e) => {
      setScrollProgress(e.progress);
      setScrollVelocity(e.velocity);
    });
    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    return () => lenis.destroy();
  }, []);

  return (
    <div className="relative min-h-screen bg-bg selection:bg-accent selection:text-bg">
      <div className="grain" />
      <VoidBackground scrollProgress={scrollProgress} scrollVelocity={scrollVelocity} />
      <Navbar />
      <main>
        <Hero />
        <Manifesto />
        <Capabilities />
        <Metrics />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
