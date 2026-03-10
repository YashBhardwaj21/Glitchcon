import { useState } from "react";
import {
  MessageCircle,
  Phone,
  UserMinus,
  Search,
  UserPlus,
  Check,
  X,
  Users,
} from "lucide-react";

const tabs = ["Online", "All", "Pending", "Blocked"];

const friends = [
  {
    id: 1,
    name: "Sarah Miller",
    avatar: "SM",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    status: "online",
    mutual: 8,
    activity: "Listening to Spotify",
  },
  {
    id: 2,
    name: "Alex Johnson",
    avatar: "AJ",
    avatarColor: "bg-gradient-to-br from-amber-400 to-orange-500",
    status: "online",
    mutual: 5,
    activity: "Playing Valorant",
  },
  {
    id: 3,
    name: "Nolan Carder",
    avatar: "NC",
    avatarColor: "bg-gradient-to-br from-indigo-400 to-violet-500",
    status: "online",
    mutual: 12,
    activity: "Working on Design chat",
  },
  {
    id: 4,
    name: "Priya Sharma",
    avatar: "PS",
    avatarColor: "bg-gradient-to-br from-fuchsia-400 to-purple-500",
    status: "idle",
    mutual: 3,
    activity: null,
  },
  {
    id: 5,
    name: "Jake Thompson",
    avatar: "JT",
    avatarColor: "bg-gradient-to-br from-sky-400 to-blue-500",
    status: "offline",
    mutual: 6,
    activity: null,
  },
  {
    id: 6,
    name: "Emily Chen",
    avatar: "EC",
    avatarColor: "bg-gradient-to-br from-emerald-400 to-teal-500",
    status: "online",
    mutual: 9,
    activity: "Editing a video",
  },
  {
    id: 7,
    name: "Marcus Lee",
    avatar: "ML",
    avatarColor: "bg-gradient-to-br from-orange-400 to-red-500",
    status: "offline",
    mutual: 2,
    activity: null,
  },
  {
    id: 8,
    name: "Olivia Davis",
    avatar: "OD",
    avatarColor: "bg-gradient-to-br from-cyan-400 to-blue-500",
    status: "online",
    mutual: 7,
    activity: "In a voice call",
  },
];

const pendingRequests = [
  {
    id: 101,
    name: "Daniel Park",
    avatar: "DP",
    avatarColor: "bg-gradient-to-br from-teal-400 to-cyan-500",
    mutual: 4,
    incoming: true,
  },
  {
    id: 102,
    name: "Lisa Wang",
    avatar: "LW",
    avatarColor: "bg-gradient-to-br from-pink-400 to-rose-500",
    mutual: 2,
    incoming: true,
  },
  {
    id: 103,
    name: "Ryan Cooper",
    avatar: "RC",
    avatarColor: "bg-gradient-to-br from-violet-400 to-purple-500",
    mutual: 1,
    incoming: false,
  },
];

const statusColor = {
  online: "bg-online",
  idle: "bg-amber-400",
  offline: "bg-gray-400",
};

export default function FriendsView() {
  const [activeTab, setActiveTab] = useState("Online");

  const filteredFriends =
    activeTab === "Online"
      ? friends.filter((f) => f.status === "online")
      : activeTab === "All"
        ? friends
        : activeTab === "Pending"
          ? pendingRequests
          : [];

  return (
    /* Main Friends Card */
    <div className="flex flex-col flex-1 min-w-0 bg-card rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Users size={20} className="text-primary" strokeWidth={2} />
            <h1 className="font-heading font-semibold text-[18px] text-text-primary">
              Friends
            </h1>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white text-[13px] font-semibold hover:bg-primary-dark transition-colors cursor-pointer">
            <UserPlus size={15} strokeWidth={2} />
            Add Friend
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-[#f0f1f4] rounded-xl p-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 px-4 rounded-lg text-[13px] font-semibold transition-all cursor-pointer ${
                activeTab === tab
                  ? "bg-white text-text-primary shadow-sm"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tab}
              {tab === "Online" && (
                <span className="ml-1.5 text-[11px] text-text-muted">
                  ({friends.filter((f) => f.status === "online").length})
                </span>
              )}
              {tab === "All" && (
                <span className="ml-1.5 text-[11px] text-text-muted">
                  ({friends.length})
                </span>
              )}
              {tab === "Pending" && (
                <span className="ml-1.5 text-[11px] text-text-muted">
                  ({pendingRequests.length})
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Search */}
      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center gap-2.5 bg-[#f0f1f4] rounded-2xl px-4 py-2.5">
          <Search size={16} className="text-text-muted flex-shrink-0" />
          <input
            type="text"
            placeholder="Search friends..."
            className="flex-1 text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
          />
        </div>
      </div>

      {/* Friend List */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {activeTab === "Blocked" ? (
          <div className="flex flex-col items-center justify-center h-full text-text-muted">
            <div className="w-16 h-16 rounded-2xl bg-[#f0f1f4] flex items-center justify-center mb-3">
              <Users size={28} strokeWidth={1.4} />
            </div>
            <p className="text-[14px] font-medium text-text-secondary">
              No blocked users
            </p>
            <p className="text-[12.5px] mt-1">
              Users you block will appear here
            </p>
          </div>
        ) : activeTab === "Pending" ? (
          <div className="space-y-1 pt-2">
            {pendingRequests.map((req) => (
              <div
                key={req.id}
                className="flex items-center gap-3 px-3 py-3 rounded-2xl hover:bg-chat-item-hover transition-colors"
              >
                <div className="relative">
                  <div
                    className={`w-11 h-11 rounded-full ${req.avatarColor} flex items-center justify-center text-white text-[12px] font-bold`}
                  >
                    {req.avatar}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-heading font-semibold text-[13.5px] text-text-primary truncate">
                    {req.name}
                  </p>
                  <p className="text-[12px] text-text-secondary">
                    {req.incoming ? "Incoming request" : "Outgoing request"} ·{" "}
                    {req.mutual} mutual
                  </p>
                </div>
                {req.incoming ? (
                  <div className="flex items-center gap-2">
                    <button className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer">
                      <Check size={16} strokeWidth={2.5} />
                    </button>
                    <button className="w-9 h-9 rounded-xl bg-danger/10 text-danger flex items-center justify-center hover:bg-danger/20 transition-colors cursor-pointer">
                      <X size={16} strokeWidth={2.5} />
                    </button>
                  </div>
                ) : (
                  <button className="w-9 h-9 rounded-xl bg-[#f0f1f4] text-text-muted flex items-center justify-center hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer">
                    <X size={16} strokeWidth={2} />
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-1 pt-2">
            {filteredFriends.map((friend) => (
              <div
                key={friend.id}
                className="flex items-center gap-3 px-3 py-3 rounded-2xl hover:bg-chat-item-hover transition-colors"
              >
                <div className="relative">
                  <div
                    className={`w-11 h-11 rounded-full ${friend.avatarColor} flex items-center justify-center text-white text-[12px] font-bold`}
                  >
                    {friend.avatar}
                  </div>
                  <div
                    className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full ${
                      statusColor[friend.status]
                    } border-2 border-card`}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-heading font-semibold text-[13.5px] text-text-primary truncate">
                    {friend.name}
                  </p>
                  <p className="text-[12px] text-text-secondary truncate">
                    {friend.activity || `${friend.mutual} mutual friends`}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <button className="w-9 h-9 rounded-xl bg-[#f0f1f4] text-text-muted flex items-center justify-center hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer">
                    <MessageCircle size={16} strokeWidth={1.8} />
                  </button>
                  <button className="w-9 h-9 rounded-xl bg-[#f0f1f4] text-text-muted flex items-center justify-center hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer">
                    <Phone size={16} strokeWidth={1.8} />
                  </button>
                  <button className="w-9 h-9 rounded-xl bg-[#f0f1f4] text-text-muted flex items-center justify-center hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer">
                    <UserMinus size={16} strokeWidth={1.8} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
