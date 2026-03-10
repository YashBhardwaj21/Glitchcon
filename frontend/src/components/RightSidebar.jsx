import { useRef, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  ChevronDown,
  Image,
  Film,
  File,
  Headphones,
  Link2,
  Mic,
  Crown,
  ShieldMinus,
  UserPlus,
  Archive,
  BellOff,
  Clock,
  CalendarDays,
  Info,
  Compass,
} from "lucide-react";

/* ── Communities data ── */
const accordionItems = [
  { icon: Image, label: "Photos", count: 36 },
  { icon: Film, label: "Videos", count: 12 },
  { icon: File, label: "Files", count: 45 },
  { icon: Headphones, label: "Audio", count: 8 },
  { icon: Link2, label: "Links", count: 23 },
  { icon: Mic, label: "Voice messages", count: 6 },
];

/* ── Friends data ── */
const activityItems = [
  {
    avatar: "EC",
    color: "bg-gradient-to-br from-emerald-400 to-teal-500",
    name: "Emily",
    action: "started editing a video",
    time: "2m ago",
    online: true,
  },
  {
    avatar: "NC",
    color: "bg-gradient-to-br from-indigo-400 to-violet-500",
    name: "Nolan",
    action: "joined Design chat",
    time: "15m ago",
    online: true,
  },
  {
    avatar: "SM",
    color: "bg-gradient-to-br from-rose-400 to-pink-500",
    name: "Sarah",
    action: "is listening to Spotify",
    time: "25m ago",
    online: true,
  },
  {
    avatar: "AJ",
    color: "bg-gradient-to-br from-amber-400 to-orange-500",
    name: "Alex",
    action: "started playing Valorant",
    time: "42m ago",
    online: true,
  },
  {
    avatar: "OD",
    color: "bg-gradient-to-br from-cyan-400 to-blue-500",
    name: "Olivia",
    action: "is in a voice call",
    time: "1h ago",
    online: true,
  },
  {
    avatar: "PS",
    color: "bg-gradient-to-br from-fuchsia-400 to-purple-500",
    name: "Priya",
    action: "went idle",
    time: "2h ago",
    online: false,
  },
];

const suggestions = [
  {
    id: 201,
    name: "Chris Evans",
    avatar: "CE",
    avatarColor: "bg-gradient-to-br from-blue-400 to-indigo-500",
    mutual: 11,
  },
  {
    id: 202,
    name: "Zara Amari",
    avatar: "ZA",
    avatarColor: "bg-gradient-to-br from-pink-400 to-fuchsia-500",
    mutual: 6,
  },
  {
    id: 203,
    name: "Leo Martinez",
    avatar: "LM",
    avatarColor: "bg-gradient-to-br from-amber-400 to-yellow-500",
    mutual: 3,
  },
  {
    id: 204,
    name: "Nina Patel",
    avatar: "NP",
    avatarColor: "bg-gradient-to-br from-emerald-400 to-green-500",
    mutual: 8,
  },
];

/* ── Archive data ── */
const archivedChats = [
  {
    id: 1,
    name: "Old Project Alpha",
    archivedDate: "Feb 28, 2026",
    muted: true,
  },
  { id: 2, name: "Hackathon 2025", archivedDate: "Jan 15, 2026", muted: true },
  {
    id: 3,
    name: "Apartment Search",
    archivedDate: "Dec 20, 2025",
    muted: false,
  },
  { id: 4, name: "Wedding Planning", archivedDate: "Nov 5, 2025", muted: true },
  {
    id: 5,
    name: "CS 301 Study Group",
    archivedDate: "Oct 18, 2025",
    muted: false,
  },
];

/* ── Top-card content per mode ── */
function CommunityTopCard() {
  return (
    <>
      <div className="px-5 pt-5 pb-4">
        <h3 className="font-heading font-semibold text-text-primary text-[15px]">
          Group Info
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {accordionItems.map(({ icon: Icon, label, count }) => (
          <button
            key={label}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl hover:bg-[#f0f1f4] transition-colors cursor-pointer"
          >
            <Icon size={16} className="text-text-muted" strokeWidth={1.7} />
            <span className="flex-1 text-left text-[13px] text-text-primary font-medium">
              {label}
            </span>
            <span className="text-[12px] text-text-muted mr-1">{count}</span>
            <ChevronDown
              size={14}
              className="text-text-muted"
              strokeWidth={2}
            />
          </button>
        ))}
      </div>
    </>
  );
}

function FriendsTopCard() {
  return (
    <>
      <div className="px-5 pt-5 pb-3">
        <h3 className="font-heading font-semibold text-text-primary text-[15px]">
          Friend Activity
        </h3>
      </div>
      <div className="px-4 pb-4 space-y-1">
        {activityItems.map((item, i) => (
          <div
            key={i}
            className="flex items-center gap-3 px-2 py-2.5 rounded-xl hover:bg-[#f0f1f4] transition-colors cursor-pointer"
          >
            <div className="relative flex-shrink-0">
              <div
                className={`w-8 h-8 rounded-full ${item.color} flex items-center justify-center text-white text-[10px] font-bold`}
              >
                {item.avatar}
              </div>
              {item.online && (
                <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-card bg-online" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] text-text-primary truncate">
                <span className="font-semibold">{item.name}</span> {item.action}
              </p>
              <p className="text-[10.5px] text-text-muted">{item.time}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

/* ── Bottom-card content per mode ── */
const avatarGradients = [
  "bg-gradient-to-br from-indigo-400 to-violet-500",
  "bg-gradient-to-br from-rose-400 to-pink-500",
  "bg-gradient-to-br from-emerald-400 to-teal-500",
  "bg-gradient-to-br from-amber-400 to-orange-500",
  "bg-gradient-to-br from-cyan-400 to-blue-500",
  "bg-gradient-to-br from-fuchsia-400 to-purple-500",
  "bg-gradient-to-br from-sky-400 to-blue-500",
  "bg-gradient-to-br from-lime-400 to-green-500",
];

function pickMemberColor(id = "") {
  let hash = 0;
  for (const ch of String(id)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return avatarGradients[hash % avatarGradients.length];
}

function getInitials(name = "") {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function CommunityBottomCard({ community, onMakeAdmin, onRemoveAdmin }) {
  const { user } = useAuth();
  const memberList = Array.isArray(community?.members) ? community.members : [];
  const totalCount = community?.total_members ?? memberList.length;

  // Determine if current user is owner
  const role = (community?.role ?? community?.userRole ?? "").toLowerCase();
  const currentUserId = user?.id ?? user?._id;
  const isOwner =
    community?.isOwner === true ||
    role === "owner" ||
    community?.owner_id === currentUserId;

  return (
    <>
      <div className="px-5 pt-5 pb-3">
        <h3 className="font-heading font-semibold text-text-primary text-[15px]">
          {totalCount} member{totalCount !== 1 ? "s" : ""}
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {memberList.length === 0 ? (
          <p className="text-center text-[12.5px] text-text-muted py-6">
            No members
          </p>
        ) : (
          memberList.map((member) => {
            const mId = member.id ?? member._id ?? member.userId;
            const name = member.name ?? member.user?.name ?? "Unknown";
            const email = member.email ?? "";
            const role = (member.role ?? "").toLowerCase();
            const isAdmin = role === "admin" || role === "owner";
            const isMemberOwner =
              role === "owner" ||
              String(mId) ===
                String(community?.owner_id ?? community?.ownerId ?? "");
            return (
              <div
                key={mId}
                className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-[#f0f1f4] transition-colors cursor-pointer"
              >
                <div className="relative flex-shrink-0">
                  <div
                    className={`w-8 h-8 rounded-full ${pickMemberColor(mId)} flex items-center justify-center text-white text-[10px] font-bold`}
                  >
                    {getInitials(name)}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="block text-[13px] text-text-primary font-medium truncate">
                    {name}
                  </span>
                  {email && (
                    <span className="block text-[11px] text-text-muted truncate">
                      {email}
                    </span>
                  )}
                </div>
                {isAdmin && (
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-primary bg-primary/8 px-2 py-0.5 rounded-full">
                      <Crown size={10} strokeWidth={2.5} />
                      {role}
                    </span>
                    {isOwner &&
                      role === "admin" &&
                      !isMemberOwner &&
                      onRemoveAdmin && (
                        <button
                          onClick={() =>
                            onRemoveAdmin(community.id ?? community._id, mId)
                          }
                          className="inline-flex items-center justify-center w-5 h-5 rounded-full text-danger/60 hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer"
                          title="Remove admin"
                        >
                          <ShieldMinus size={12} strokeWidth={2.5} />
                        </button>
                      )}
                  </div>
                )}
                {isOwner && !isAdmin && onMakeAdmin && (
                  <button
                    onClick={() =>
                      onMakeAdmin(community.id ?? community._id, mId)
                    }
                    className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full hover:bg-emerald-500/20 transition-colors cursor-pointer"
                    title="Make admin"
                  >
                    <Crown size={10} strokeWidth={2.5} />
                    Make Admin
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </>
  );
}

function FriendsBottomCard() {
  return (
    <>
      <div className="px-5 pt-5 pb-3">
        <h3 className="font-heading font-semibold text-text-primary text-[15px]">
          People You May Know
        </h3>
        <p className="text-[12px] text-text-secondary mt-0.5">
          Based on mutual friends
        </p>
      </div>
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {suggestions.map((person) => (
          <div
            key={person.id}
            className="flex flex-col items-center p-4 rounded-2xl hover:bg-chat-item-hover transition-colors mb-1"
          >
            <div
              className={`w-14 h-14 rounded-full ${person.avatarColor} flex items-center justify-center text-white text-[15px] font-bold mb-2.5`}
            >
              {person.avatar}
            </div>
            <p className="font-heading font-semibold text-[13px] text-text-primary text-center">
              {person.name}
            </p>
            <p className="text-[11.5px] text-text-muted mb-3">
              {person.mutual} mutual friends
            </p>
            <button className="w-full py-2 rounded-xl bg-primary/10 text-primary text-[12.5px] font-semibold hover:bg-primary/20 transition-colors cursor-pointer">
              Add Friend
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

/* ── Archive cards ── */
function ArchiveTopCard() {
  return (
    <>
      <div className="px-5 pt-5 pb-4">
        <h3 className="font-heading font-semibold text-text-primary text-[15px] mb-4">
          Archive Overview
        </h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 px-2 py-2.5 rounded-xl bg-[#f0f1f4]">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
              <Archive size={16} className="text-primary" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-text-primary">
                {archivedChats.length} Chats
              </p>
              <p className="text-[11px] text-text-muted">Total archived</p>
            </div>
          </div>
          <div className="flex items-center gap-3 px-2 py-2.5 rounded-xl bg-[#f0f1f4]">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <BellOff size={16} className="text-amber-500" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-text-primary">
                {archivedChats.filter((c) => c.muted).length} Muted
              </p>
              <p className="text-[11px] text-text-muted">Notifications off</p>
            </div>
          </div>
          <div className="flex items-center gap-3 px-2 py-2.5 rounded-xl bg-[#f0f1f4]">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <Clock size={16} className="text-emerald-500" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-text-primary">
                Oldest
              </p>
              <p className="text-[11px] text-text-muted">Oct 18, 2025</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ArchiveBottomCard() {
  return (
    <>
      <div className="px-5 pt-5 pb-3">
        <h3 className="font-heading font-semibold text-text-primary text-[15px]">
          Recent Activity
        </h3>
        <p className="text-[12px] text-text-secondary mt-0.5">
          Archive history
        </p>
      </div>
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-1">
        {archivedChats.map((chat) => (
          <div
            key={chat.id}
            className="flex items-center gap-3 px-2 py-2.5 rounded-xl hover:bg-[#f0f1f4] transition-colors cursor-pointer"
          >
            <div className="w-8 h-8 rounded-xl bg-primary/8 flex items-center justify-center flex-shrink-0">
              <CalendarDays
                size={14}
                className="text-primary"
                strokeWidth={1.8}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] text-text-primary truncate">
                <span className="font-semibold">{chat.name}</span> archived
              </p>
              <p className="text-[10.5px] text-text-muted">
                {chat.archivedDate}
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="px-4 py-3 border-t border-border">
        <div className="flex items-start gap-2">
          <Info
            size={13}
            className="text-text-muted flex-shrink-0 mt-0.5"
            strokeWidth={1.8}
          />
          <p className="text-[11px] text-text-muted leading-relaxed">
            Archived chats are removed after 1 year of inactivity
          </p>
        </div>
      </div>
    </>
  );
}

/* ── Discover detail card ── */
const topicColors = {
  Tech: "bg-blue-500/10 text-blue-600",
  Social: "bg-pink-500/10 text-pink-600",
  Study: "bg-amber-500/10 text-amber-600",
  Gaming: "bg-emerald-500/10 text-emerald-600",
  Others: "bg-violet-500/10 text-violet-600",
};

function DiscoverDetailCard({ community }) {
  if (!community) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 px-5 text-center">
        <Compass
          size={32}
          className="text-text-muted/30 mb-3"
          strokeWidth={1.5}
        />
        <p className="text-[13px] text-text-muted font-medium">
          Select a community to view details
        </p>
      </div>
    );
  }

  const initials = (community.name ?? "")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const topic = community.topic || community.category || "Others";
  const topicStyle = topicColors[topic] || topicColors.Others;
  const createdRaw = community.created_at ?? community.createdAt;
  const created = createdRaw
    ? new Date(createdRaw).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "Unknown";

  return (
    <div className="flex flex-col flex-1 overflow-y-auto">
      {/* Header with avatar */}
      <div className="flex flex-col items-center pt-6 pb-4 px-5">
        {community.image || community.picture ? (
          <img
            src={community.image || community.picture}
            alt={community.name}
            className="w-16 h-16 rounded-2xl object-cover shadow-md mb-3"
          />
        ) : (
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-violet-500 flex items-center justify-center text-white text-[20px] font-bold shadow-md mb-3">
            {initials}
          </div>
        )}
        <h3 className="font-heading font-semibold text-[16px] text-text-primary text-center">
          {community.name}
        </h3>
        <span
          className={`mt-2 px-3 py-1 rounded-full text-[11px] font-semibold ${topicStyle}`}
        >
          {topic}
        </span>
      </div>

      {/* Description */}
      <div className="px-5 pb-4">
        <p className="text-[12.5px] text-text-secondary leading-relaxed">
          {community.description || "No description provided."}
        </p>
      </div>

      {/* Stats */}
      <div className="px-4 space-y-1.5">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[#f0f1f4]">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <CalendarDays
              size={14}
              className="text-primary"
              strokeWidth={1.8}
            />
          </div>
          <div>
            <p className="text-[12.5px] font-semibold text-text-primary">
              Created
            </p>
            <p className="text-[11px] text-text-muted">{created}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[#f0f1f4]">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <UserPlus size={14} className="text-blue-500" strokeWidth={1.8} />
          </div>
          <div>
            <p className="text-[12.5px] font-semibold text-text-primary">
              {community.total_members ?? community.memberCount ?? "—"} Members
            </p>
            <p className="text-[11px] text-text-muted">Total members</p>
          </div>
        </div>

        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[#f0f1f4]">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-online" />
          </div>
          <div>
            <p className="text-[12.5px] font-semibold text-text-primary">
              {community.online_members ?? community.onlineCount ?? "—"} Online
            </p>
            <p className="text-[11px] text-text-muted">Currently active</p>
          </div>
        </div>
      </div>

      <div className="flex-1" />
    </div>
  );
}

function DiscoverEmptyBottom() {
  return null;
}

/* ── Flex ratios per mode ── */
const topFlex = { communities: 9, friends: 6, archive: 4, discover: 1 };
const bottomFlex = { communities: 11, friends: 4, archive: 6, discover: 0 };

const topContent = {
  communities: CommunityTopCard,
  friends: FriendsTopCard,
  archive: ArchiveTopCard,
  discover: DiscoverDetailCard,
};
const bottomContent = {
  communities: CommunityBottomCard,
  friends: FriendsBottomCard,
  archive: ArchiveBottomCard,
  discover: DiscoverEmptyBottom,
};

/* ── Unified sidebar with animated split ── */
export default function RightSidebar({
  mode = "communities",
  discoverCommunity = null,
  activeCommunity = null,
  onMakeAdmin,
  onRemoveAdmin,
}) {
  const topRef = useRef(null);
  const bottomRef = useRef(null);
  const [rendered, setRendered] = useState(mode);
  const prevModeRef = useRef(mode);

  // Animate flex changes via direct style mutation so CSS transition can interpolate
  useEffect(() => {
    const prevMode = prevModeRef.current;
    prevModeRef.current = mode;

    // Longer duration when transitioning FROM discover (more distance to cover)
    const fromDiscover = prevMode === "discover" && mode !== "discover";
    const duration = fromDiscover ? "2000ms" : "500ms";

    const tf = topFlex[mode] ?? 5;
    const bf = bottomFlex[mode] ?? 5;

    if (topRef.current) {
      topRef.current.style.transition = `flex ${duration} cubic-bezier(0.4, 0, 0.2, 1)`;
      topRef.current.style.flex = `${tf} 1 0%`;
    }
    if (bottomRef.current) {
      bottomRef.current.style.transition = `flex ${duration} cubic-bezier(0.4, 0, 0.2, 1)`;
      bottomRef.current.style.flex = `${bf} 1 0%`;
    }

    // Swap card content after a brief delay so the resize starts before content pops in
    const timer = setTimeout(() => setRendered(mode), 80);
    return () => clearTimeout(timer);
  }, [mode]);

  const TopComp = topContent[rendered] ?? CommunityTopCard;
  const BottomComp = bottomContent[rendered] ?? CommunityBottomCard;

  const initTop = topFlex[mode] ?? 5;
  const initBottom = bottomFlex[mode] ?? 5;
  const isDiscover = rendered === "discover";

  return (
    <div className="flex flex-col w-[260px] min-w-[260px] gap-3 overflow-hidden">
      {/* Top Card */}
      <div
        ref={topRef}
        className="bg-card rounded-3xl overflow-hidden flex flex-col min-h-0"
        style={{
          flex: `${initTop} 1 0%`,
          transition: "flex 500ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {isDiscover ? (
          <DiscoverDetailCard community={discoverCommunity} />
        ) : (
          <TopComp />
        )}
      </div>

      {/* Bottom Card — hidden for discover via flex 0 */}
      <div
        ref={bottomRef}
        className="bg-card rounded-3xl overflow-hidden flex flex-col min-h-0"
        style={{
          flex: `${initBottom} 1 0%`,
          transition: "flex 500ms cubic-bezier(0.4, 0, 0.2, 1)",
          ...(initBottom === 0 ? { padding: 0, margin: 0, gap: 0 } : {}),
        }}
      >
        {!isDiscover && (
          <BottomComp
            community={activeCommunity}
            onMakeAdmin={onMakeAdmin}
            onRemoveAdmin={onRemoveAdmin}
          />
        )}
      </div>
    </div>
  );
}
