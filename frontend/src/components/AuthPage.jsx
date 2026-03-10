import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  Camera,
  X,
  Mail,
  Lock,
  User,
  Zap,
  ShieldCheck,
  Users,
} from "lucide-react";

// Import your custom background component
import LightRays from "./LightRays";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);

  const [avatar, setAvatar] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const avatarInputRef = useRef(null);

  const { login, register, loading, error, setError } = useAuth();
  const navigate = useNavigate();

  const toggle = () => {
    setIsLogin((v) => !v);
    setAvatar(null);
    setAvatarPreview(null);
    setError(null);
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("Avatar must be under 5 MB");
      return;
    }
    setAvatar(file);
    setAvatarPreview(URL.createObjectURL(file));
  };

  const removeAvatar = () => {
    setAvatar(null);
    setAvatarPreview(null);
    if (avatarInputRef.current) avatarInputRef.current.value = "";
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(name, email, password, avatar);
      }
      navigate("/", { replace: true });
    } catch {
      /* error is already set in context */
    }
  };

  return (
    <div className="relative w-screen min-h-screen overflow-x-hidden overflow-y-auto font-body bg-[#131315]">
      {/* ── LAYER 1: Custom LightRays Background ── */}
      <div className="fixed inset-0 pointer-events-none z-[1] mix-blend-screen">
        <LightRays
          raysOrigin="top-left"
          raysColor="#ffffff"
          raysSpeed={1}
          lightSpread={1.8}
          rayLength={2.5}
          followMouse={true}
          mouseInfluence={0.1}
          noiseAmount={0.03}
          distortion={0.05}
          className="opacity-[0.7]"
          pulsating={true}
          fadeDistance={1}
          saturation={1}
        />
      </div>

      {/* ── LAYER 10: Content ── */}
      <div className="relative z-[10] min-h-screen w-full flex items-center justify-center p-6">
        <div className="w-full max-w-[1100px] grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          {/* ── Left Side - Brand and Value Proposition ── */}
          <div className="hidden lg:flex flex-col justify-center space-y-10">
            {/* Brand */}
            <div className="cursor-pointer" onClick={() => navigate("/")}>
              <div className="flex items-center gap-3 mb-6">
                <i className="fas fa-circle-nodes text-[#7678ed] text-[32px] drop-shadow-[0_0_15px_rgba(118,120,237,0.5)]"></i>
                <h1 className="font-heading font-bold text-[36px] text-white tracking-tight">
                  Commons
                </h1>
              </div>
              <p className="text-[18px] text-white/50 leading-relaxed max-w-md font-medium">
                The standard for safe spaces. Build thriving communities
                protected by invisible, intelligent moderation.
              </p>
            </div>

            {/* Value Props */}
            <div className="space-y-6 pt-4">
              {[
                {
                  icon: Zap,
                  title: "Real-time Messaging",
                  desc: "Instant WebSocket delivery with live presence.",
                  color: "text-blue-400",
                  bg: "bg-blue-500/10 border-blue-500/20",
                },
                {
                  icon: ShieldCheck,
                  title: "AI Moderation",
                  desc: "ML-powered content filtering built natively in.",
                  color: "text-violet-400",
                  bg: "bg-violet-500/10 border-violet-500/20",
                },
                {
                  icon: Users,
                  title: "Community First",
                  desc: "Role-based access and granular permissions.",
                  color: "text-emerald-400",
                  bg: "bg-emerald-500/10 border-emerald-500/20",
                },
              ].map((prop, i) => (
                <div key={i} className="flex gap-5 items-center group">
                  <div
                    className={`w-12 h-12 rounded-2xl flex items-center justify-center border ${prop.bg} transition-all duration-300 group-hover:scale-110`}
                  >
                    <prop.icon size={22} className={prop.color} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-[16px] tracking-wide">
                      {prop.title}
                    </h3>
                    <p className="text-white/40 text-[14px] mt-0.5">
                      {prop.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right Side - Auth Form ── */}
          <div className="w-full max-w-[440px] mx-auto lg:mx-0">
            {/* Mobile Brand */}
            <div
              className="lg:hidden flex flex-col items-center justify-center gap-4 mb-10 cursor-pointer"
              onClick={() => navigate("/")}
            >
              <i className="fas fa-circle-nodes text-[#7678ed] text-[40px] drop-shadow-[0_0_15px_rgba(118,120,237,0.5)]"></i>
              <h1 className="font-heading font-bold text-[32px] text-white tracking-tight">
                Commons
              </h1>
            </div>

            {/* Premium Auth Card */}
            <div className="bg-[#1a1a1d]/80 backdrop-blur-xl border border-white/[0.06] rounded-[2.5rem] p-8 sm:p-10 shadow-2xl shadow-black/80 relative overflow-hidden">
              {/* Subtle top card glow */}
              <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

              {/* Tab Switcher */}
              <div className="flex bg-black/40 border border-white/5 rounded-2xl p-1.5 mb-8 shadow-inner">
                <button
                  type="button"
                  onClick={() => {
                    setIsLogin(true);
                    setError(null);
                  }}
                  className={`flex-1 py-2.5 rounded-xl text-[14px] font-semibold transition-all duration-300 ${
                    isLogin
                      ? "bg-[#2a2a2e] text-white shadow-md border border-white/10"
                      : "text-white/40 hover:text-white/70"
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsLogin(false);
                    setError(null);
                  }}
                  className={`flex-1 py-2.5 rounded-xl text-[14px] font-semibold transition-all duration-300 ${
                    !isLogin
                      ? "bg-[#2a2a2e] text-white shadow-md border border-white/10"
                      : "text-white/40 hover:text-white/70"
                  }`}
                >
                  Sign Up
                </button>
              </div>

              {/* Heading */}
              <div className="mb-8 text-center">
                <h2 className="font-heading font-bold text-[28px] text-white tracking-tight mb-2">
                  {isLogin ? "Welcome back" : "Create an account"}
                </h2>
                <p className="text-white/40 text-[14px] font-medium">
                  {isLogin
                    ? "Enter your credentials to access your spaces."
                    : "Join the next generation of online communities."}
                </p>
              </div>

              {/* Error Banner */}
              {error && (
                <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-[13px] font-medium flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
                  {error}
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {!isLogin && (
                  <>
                    {/* Sleek Circular Avatar Upload */}
                    <div className="mb-6 flex flex-col items-center">
                      <div className="relative group">
                        <input
                          ref={avatarInputRef}
                          type="file"
                          accept="image/*"
                          onChange={handleAvatarChange}
                          className="hidden"
                        />
                        <div
                          onClick={() => avatarInputRef.current?.click()}
                          className={`w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 overflow-hidden border-2 ${
                            avatarPreview
                              ? "border-[#7678ed]"
                              : "border-white/10 border-dashed bg-black/40 group-hover:border-[#7678ed]/50 group-hover:bg-[#7678ed]/10"
                          }`}
                        >
                          {avatarPreview ? (
                            <img
                              src={avatarPreview}
                              alt="Avatar preview"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <Camera
                              size={24}
                              className="text-white/30 group-hover:text-[#7678ed] transition-colors"
                            />
                          )}
                        </div>
                        {avatarPreview && (
                          <button
                            type="button"
                            onClick={removeAvatar}
                            className="absolute 0 right-0 w-6 h-6 rounded-full bg-[#1a1a1d] border border-white/10 text-white flex items-center justify-center hover:bg-red-500 hover:border-red-500 transition-all cursor-pointer shadow-lg"
                          >
                            <X size={12} strokeWidth={3} />
                          </button>
                        )}
                      </div>
                      <p className="text-[12px] text-white/30 font-medium mt-3">
                        {avatarPreview
                          ? "Looking good!"
                          : "Upload profile photo (optional)"}
                      </p>
                    </div>

                    {/* Name Input */}
                    <div className="relative group">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-white/30 group-focus-within:text-[#7678ed] transition-colors">
                        <User size={18} />
                      </div>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Full name"
                        required={!isLogin}
                        className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-black/40 border border-white/5 text-[14px] text-white placeholder:text-white/30 outline-none focus:border-[#7678ed]/50 focus:ring-2 focus:ring-[#7678ed]/20 transition-all font-medium"
                      />
                    </div>
                  </>
                )}

                {/* Email Input */}
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-white/30 group-focus-within:text-[#7678ed] transition-colors">
                    <Mail size={18} />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email address"
                    required
                    className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-black/40 border border-white/5 text-[14px] text-white placeholder:text-white/30 outline-none focus:border-[#7678ed]/50 focus:ring-2 focus:ring-[#7678ed]/20 transition-all font-medium"
                  />
                </div>

                {/* Password Input */}
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-white/30 group-focus-within:text-[#7678ed] transition-colors">
                    <Lock size={18} />
                  </div>
                  <input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    required
                    minLength={6}
                    className="w-full pl-11 pr-12 py-3.5 rounded-xl bg-black/40 border border-white/5 text-[14px] text-white placeholder:text-white/30 outline-none focus:border-[#7678ed]/50 focus:ring-2 focus:ring-[#7678ed]/20 transition-all font-medium"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-white/30 hover:text-white/70 transition-colors cursor-pointer"
                  >
                    {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>

                {isLogin && (
                  <div className="flex justify-end pt-1">
                    <button
                      type="button"
                      className="text-[13px] text-[#7678ed] hover:text-[#8b8df0] font-semibold transition-colors cursor-pointer"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-4 rounded-xl bg-[#7678ed] text-white font-bold text-[15px] hover:bg-[#6062df] active:scale-[0.98] transition-all shadow-[0_0_20px_rgba(118,120,237,0.3)] hover:shadow-[0_0_25px_rgba(118,120,237,0.5)] disabled:opacity-50 disabled:cursor-not-allowed mt-6 cursor-pointer group"
                >
                  {loading ? (
                    <Loader2 size={20} className="animate-spin" />
                  ) : (
                    <>
                      {isLogin ? "Sign In" : "Create Account"}
                      <ArrowRight
                        size={18}
                        strokeWidth={2.5}
                        className="group-hover:translate-x-1 transition-transform"
                      />
                    </>
                  )}
                </button>
              </form>

              {/* Bottom Toggle */}
              <p className="text-center text-[14px] text-white/40 mt-8 font-medium">
                {isLogin
                  ? "Don't have an account?"
                  : "Already have an account?"}{" "}
                <button
                  type="button"
                  onClick={toggle}
                  className="text-[#7678ed] font-bold hover:text-[#8b8df0] transition-colors cursor-pointer ml-1"
                >
                  {isLogin ? "Sign up now" : "Sign in"}
                </button>
              </p>
            </div>

            {/* Sub Footer */}
            <p className="text-center text-[12px] text-white/20 mt-8 font-medium">
              By continuing, you agree to Commons' Terms of Service and Privacy
              Policy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
