import { useNavigate } from "react-router-dom";
import { useRef } from "react";
import CircularGallery from "./CircularGallery";
import {
  ArrowRight,
  Shield,
  Users,
  MessageCircle,
  Sparkles,
  Globe,
  Lock,
  Zap,
  ChevronRight,
  Bot,
} from "lucide-react";

// Import your custom background component
import LightRays from "./LightRays";

// ── Custom 3D Tilt Video Component ──
const TiltVideo = ({ src }) => {
  const tiltRef = useRef(null);

  const handleMouseMove = (e) => {
    if (!tiltRef.current) return;
    const { left, top, width, height } =
      tiltRef.current.getBoundingClientRect();

    const x = (e.clientX - left) / width - 0.5;
    const y = (e.clientY - top) / height - 0.5;

    tiltRef.current.style.transform = `perspective(1200px) rotateY(${x * 12}deg) rotateX(${-y * 12}deg) scale3d(1.02, 1.02, 1.02)`;
  };

  const handleMouseLeave = () => {
    if (!tiltRef.current) return;
    tiltRef.current.style.transform = `perspective(1200px) rotateY(0deg) rotateX(0deg) scale3d(1, 1, 1)`;
  };

  return (
    <div
      ref={tiltRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="w-full max-w-5xl rounded-3xl overflow-hidden transition-transform duration-200 ease-out cursor-crosshair"
      style={{ transformStyle: "preserve-3d", lineHeight: 0 }}
    >
      <video
        src={src}
        autoPlay
        loop
        muted
        playsInline
        className="w-full h-auto block m-0 p-0"
      />
    </div>
  );
};

const stats = [
  { value: "ML", label: "Content Moderation" },
  { value: "Real-time", label: "Messaging" },
  { value: "Role-based", label: "Access Control" },
  { value: "Open", label: "Communities" },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {/* ── LAYER 0: Solid Background ── */}
      <div className="fixed inset-0 bg-[#202022] z-[0]" />
      {/* ── LAYER 1: Custom LightRays Background ── */}
      <div className="fixed inset-0 pointer-events-none z-[1] mix-blend-screen">
        <LightRays
          raysOrigin="top-center"
          raysColor="#ffffff"
          raysSpeed={1.2}
          lightSpread={1.5}
          rayLength={2.5}
          followMouse={true}
          mouseInfluence={0.15}
          noiseAmount={0.05}
          distortion={0.1}
          className="opacity-70"
          pulsating={true}
          fadeDistance={1}
          saturation={1}
        />
      </div>
      {/* ── LAYER 10: Scrollable Content ── */}
      <div className="relative z-[10] h-full w-full overflow-y-auto overflow-x-hidden text-text-light">
        {/* ── Modern Navigation ── */}
        <nav className="relative flex items-center justify-between px-8 md:px-20 py-6 bg-transparent backdrop-blur-lg border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center">
              <i className="fas fa-circle-nodes text-primary text-3xl"></i>
            </div>
            <span className="font-heading font-bold text-[24px] text-white tracking-tight">
              Commons
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/auth")}
              className="px-6 py-2 rounded-lg text-[14px] font-semibold text-white/80 hover:text-white transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={() => navigate("/auth")}
              className="px-6 py-2 rounded-lg bg-primary text-white text-[14px] font-semibold hover:bg-primary-dark shadow-md shadow-primary/20 transition-all"
            >
              Get Started
            </button>
          </div>
        </nav>
        {/* ── Modern Hero ── */}
        <section className="relative flex flex-col items-center justify-center text-center px-8 pt-24 pb-24 gap-8">
          <h1 className="font-heading font-bold text-[48px] md:text-[64px] leading-[1.1] tracking-tight max-w-4xl">
            Where
            <span className="bg-gradient-to-r from-primary-light to-badge bg-clip-text text-transparent mx-2">
              conversations
            </span>
            stay respectful
          </h1>
          <p className="mt-4 text-[18px] md:text-[20px] text-text-light/70 max-w-2xl mx-auto leading-relaxed">
            Build communities with built-in AI moderation. Commons keeps
            discussions productive, safe, and genuinely welcoming for everyone.
          </p>
          <div className="flex flex-col sm:flex-row items-center gap-4 mt-8">
            <button
              onClick={() => navigate("/auth")}
              className="group flex items-center gap-3 px-8 py-4 rounded-2xl bg-primary text-white font-semibold text-[16px] hover:bg-primary-dark shadow-xl shadow-primary/30 transition-all"
            >
              Get Started Free
              <ArrowRight
                size={20}
                className="group-hover:translate-x-1 transition-transform"
              />
            </button>
            <button
              onClick={() => {
                document
                  .getElementById("features")
                  ?.scrollIntoView({ behavior: "smooth" });
              }}
              className="flex items-center gap-2 px-8 py-4 rounded-2xl bg-white/10 border border-white/20 text-white/80 font-semibold text-[16px] hover:bg-white/20 hover:text-white transition-all backdrop-blur-sm"
            >
              Learn More
            </button>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-10 mt-16">
            {stats.map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-[28px] font-heading font-bold text-white">
                  {s.value}
                </div>
                <div className="text-[13px] text-text-light/40 font-medium mt-1">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </section>
        {/* ── App preview mockup (unchanged) ── */}
        <section className="relative flex justify-center px-8 pb-24 perspective-1000">
          <TiltVideo src="/demo.webm" />
        </section>
        {/* ── Custom Keyframes for Feature Animations (unchanged) ── */}
        <style
          dangerouslySetInnerHTML={{
            __html: `
          @keyframes scan {
            0%, 100% { transform: translateY(-10px); opacity: 0; }
            10%, 90% { opacity: 1; }
            50% { transform: translateY(110px); }
          }
          @keyframes ripple {
            0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
            70% { box-shadow: 0 0 0 30px rgba(245, 158, 11, 0); }
            100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
          }
          @keyframes bounce-delay {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-6px); }
          }
          @keyframes orbit {
            0% { transform: rotate(0deg) translateX(35px) rotate(0deg); }
            100% { transform: rotate(360deg) translateX(35px) rotate(-360deg); }
          }
        `,
          }}
        />
        {/* ── Modern Features Section ── */}
        <section id="features" className="relative px-8 md:px-20 py-32">
          <div className="text-center mb-20">
            <span className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6 backdrop-blur-sm">
              <Zap size={15} className="text-primary-light" />
              <span className="text-[13px] font-semibold text-primary-light tracking-wide">
                THE COMMONS ADVANTAGE
              </span>
            </span>
            <h2 className="font-heading font-bold text-[36px] md:text-[48px] text-white tracking-tight">
              Next-generation tools for modern communities
            </h2>
          </div>
          <div style={{ height: "600px", position: "relative" }}>
            <CircularGallery
              bend={1}
              textColor="#ffffff"
              borderRadius={0.05}
              scrollSpeed={1}
              scrollEase={0.05}
            />
          </div>
        </section>
        {/* ── Modern How It Works Section ── */}
        <section className="relative px-8 md:px-20 py-24">
          <div className="text-center mb-16">
            <h2 className="font-heading font-bold text-[36px] md:text-[48px] text-white tracking-tight">
              Get started in minutes
            </h2>
            <p className="mt-4 text-[16px] text-text-light/60 max-w-lg mx-auto">
              Three simple steps to join the revolution of safe, AI-moderated
              community communication.
            </p>
          </div>
          <div className="flex flex-col md:flex-row items-stretch gap-8 max-w-5xl mx-auto">
            {[
              {
                step: "01",
                title: "Create an Account",
                desc: "Sign up in seconds. No credit card required.",
                icon: Globe,
              },
              {
                step: "02",
                title: "Create or Join",
                desc: "Start your own community or discover existing ones.",
                icon: Users,
              },
              {
                step: "03",
                title: "Chat Safely",
                desc: "AI moderation works in the background, keeping things civil.",
                icon: MessageCircle,
              },
            ].map((s, i) => (
              <div
                key={s.step}
                className="flex-1 relative p-8 rounded-2xl bg-white/[0.03] border border-white/[0.06] backdrop-blur-sm shadow-md"
              >
                <span className="text-[56px] font-heading font-bold text-primary/15 absolute top-4 right-6 leading-none select-none">
                  {s.step}
                </span>
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  <s.icon size={22} className="text-primary-light" />
                </div>
                <h3 className="font-heading font-semibold text-[18px] text-white mb-2">
                  {s.title}
                </h3>
                <p className="text-[14px] text-text-light/45 leading-relaxed">
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </section>
        {/* ── Modern CTA Banner ── */}
        <section className="relative px-8 md:px-20 py-24">
          <div className="max-w-5xl mx-auto rounded-3xl overflow-hidden relative border border-white/10 shadow-2xl shadow-primary/20">
            <div className="absolute inset-0 bg-gradient-to-br from-primary via-primary-dark to-[#202022]" />
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImEiIHBhdHRlcm5Vbml0cz0idXNlclNwYWNlT25Vc2UiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMSIgZmlsbD0icmdiYSgyNTUsMjU1LDI1NSwwLjA1KSIvPjwvcGF0dGVybj48L2RlZnM+PHJlY3QgZmlsbD0idXJsKCNhKSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIvPjwvc3ZnPg==')] opacity-40" />
            <div className="relative flex flex-col items-center text-center px-12 py-20 md:py-24 backdrop-blur-sm">
              <h2 className="font-heading font-bold text-[32px] md:text-[44px] text-white tracking-tight max-w-xl">
                Ready to build a better community?
              </h2>
              <p className="mt-6 text-[18px] text-white/80 max-w-lg">
                Join Commons today and experience discussions where everyone
                feels welcome and heard.
              </p>
              <button
                onClick={() => navigate("/auth")}
                className="group mt-10 flex items-center gap-3 px-10 py-5 rounded-2xl bg-white text-primary font-bold text-[16px] hover:bg-gray-50 shadow-xl shadow-black/20 transition-all"
              >
                Get Started Free
                <ChevronRight
                  size={20}
                  className="group-hover:translate-x-1 transition-transform"
                />
              </button>
            </div>
          </div>
        </section>
        {/* ── Modern Footer ── */}
        <footer className="relative border-t border-white/[0.06] px-8 md:px-20 py-10 backdrop-blur-md bg-dark/50">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 max-w-5xl mx-auto">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                <i className="fas fa-circle-nodes text-primary-light text-[15px]"></i>
              </div>
              <span className="font-heading font-semibold text-[16px] text-text-light/60">
                Commons
              </span>
            </div>
            <p className="text-[13px] text-text-light/30">
              &copy; {new Date().getFullYear()} Commons. All rights reserved.
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
