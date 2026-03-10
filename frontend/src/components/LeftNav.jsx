import {
  MessageCircle,
  Building2,
  Users,
  Compass,
  Archive,
  Pencil,
  LogOut,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const navItems = [
  {
    icon: MessageCircle,
    label: "Direct Message",
    view: "direct_message",
    badge: 12,
  },
  { icon: Compass, label: "Discover", view: "discover", badge: 5 },
  { icon: Building2, label: "Communities", view: "communities", badge: 3 },
  { icon: Users, label: "Friends", view: "friends", badge: null },
  { icon: Archive, label: "Archive", view: "archive", badge: null },
];

const bottomActions = [
  { icon: Pencil, label: "Edit" },
  { icon: LogOut, label: "Log out" },
];

export default function LeftNav({ activeView, onViewChange, onLogout }) {
  const { user } = useAuth();
  const avatarUrl = user?.avatar_url;
  const initials = (user?.name ?? "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="flex flex-col items-center w-[72px] min-w-[72px] py-6 gap-2">
      {/* Brand Logo */}
      <div className="flex items-center justify-center mb-5">
        <i className="fas fa-circle-nodes text-primary text-3xl"></i>
      </div>
      {/* Nav Icons */}
      <div className="flex flex-col items-center gap-1 flex-1">
        {navItems.map(({ icon: Icon, label, view, badge }) => {
          const isActive = activeView === view;
          return (
            <button
              key={label}
              title={label}
              onClick={() => onViewChange(view)}
              className={`relative w-11 h-11 rounded-2xl flex items-center justify-center transition-all cursor-pointer ${
                isActive
                  ? "bg-primary text-white shadow-md shadow-primary/20"
                  : "text-[#8a8a9a] hover:bg-white/8 hover:text-white"
              }`}
            >
              <Icon size={20} strokeWidth={isActive ? 2 : 1.6} />
              {badge && (
                <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-badge text-white text-[10px] font-bold flex items-center justify-center px-1 shadow-sm">
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Actions */}
      <div className="flex flex-col items-center gap-1 pt-3 border-t border-white/8">
        {/* Profile avatar */}
        <button
          title="Profile"
          className="w-11 h-11 rounded-2xl flex items-center justify-center overflow-hidden hover:ring-2 hover:ring-primary/40 transition-all cursor-pointer"
        >
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt="Profile"
              className="w-full h-full object-cover rounded-2xl"
            />
          ) : (
            <div className="w-full h-full rounded-2xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center text-white text-[12px] font-bold">
              {initials}
            </div>
          )}
        </button>
        {bottomActions.map(({ icon: Icon, label }) => (
          <button
            key={label}
            title={label}
            onClick={label === "Log out" ? onLogout : undefined}
            className="w-11 h-11 rounded-2xl flex items-center justify-center text-[#8a8a9a] hover:bg-white/8 hover:text-white transition-all cursor-pointer"
          >
            <Icon size={19} strokeWidth={1.6} />
          </button>
        ))}
      </div>
    </div>
  );
}
