import { useState, useEffect } from "react";
import { Search, Users, Compass, Loader2, CalendarDays } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getCommunities } from "../api";

const topics = ["All", "Tech", "Social", "Study", "Gaming", "Others"];

const topicColors = {
  Tech: "bg-blue-500/10 text-blue-600",
  Social: "bg-pink-500/10 text-pink-600",
  Study: "bg-amber-500/10 text-amber-600",
  Gaming: "bg-emerald-500/10 text-emerald-600",
  Others: "bg-violet-500/10 text-violet-600",
};

function getInitials(name = "") {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export default function DiscoverView({
  onJoinCommunity,
  onSelectCommunity,
  myCommunities = [],
}) {
  const { token } = useAuth();
  const [communities, setCommunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTopic, setActiveTopic] = useState("All");
  const [joiningId, setJoiningId] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  /* Fetch all communities for discovery */
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getCommunities(token)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.communities ?? []);
        setCommunities(list);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  const handleJoin = async (e, communityId) => {
    e.stopPropagation();
    if (joiningId) return;
    setJoiningId(communityId);
    try {
      await onJoinCommunity?.(communityId);
      setCommunities((prev) =>
        prev.map((c) =>
          (c.id ?? c._id) === communityId ? { ...c, joined: true } : c,
        ),
      );
    } catch {
      /* silent */
    } finally {
      setJoiningId(null);
    }
  };

  const handleSelect = (community) => {
    const cId = community.id ?? community._id;
    setSelectedId(cId);
    onSelectCommunity?.(community);
  };

  const filtered = communities.filter((c) => {
    const cId = c.id ?? c._id;
    const alreadyJoined = myCommunities.some((mc) => (mc.id ?? mc._id) === cId);
    if (alreadyJoined) return false;
    const matchesSearch =
      !searchQuery ||
      c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const topic = c.topic || c.category || "Others";
    const matchesTopic = activeTopic === "All" || topic === activeTopic;
    return matchesSearch && matchesTopic;
  });

  return (
    <div className="flex flex-col flex-1 min-w-0 bg-card rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Compass size={22} className="text-primary" strokeWidth={2} />
            <div>
              <h1 className="font-heading font-semibold text-[18px] text-text-primary">
                Discover Communities
              </h1>
              <p className="text-[12.5px] text-text-secondary mt-0.5">
                Find your people and join the conversation
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-text-muted">
            <Users size={16} strokeWidth={1.8} />
            <span className="text-[12.5px] font-medium">
              {communities.length} communities
            </span>
          </div>
        </div>

        {/* Search */}
        <div className="flex items-center gap-2.5 bg-[#f0f1f4] rounded-2xl px-4 py-3 mb-4">
          <Search size={17} className="text-text-muted flex-shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search communities..."
            className="flex-1 text-[13.5px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
          />
        </div>

        {/* Topic Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {topics.map((t) => (
            <button
              key={t}
              onClick={() => setActiveTopic(t)}
              className={`px-4 py-2 rounded-xl text-[12.5px] font-semibold whitespace-nowrap transition-all cursor-pointer ${
                activeTopic === t
                  ? "bg-primary text-white shadow-md shadow-primary/20"
                  : "bg-[#f0f1f4] text-text-secondary hover:bg-[#e8e9ec] hover:text-text-primary"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Community Grid */}
      <div className="flex-1 overflow-y-auto p-5">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={28} className="animate-spin text-primary" />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {filtered.map((community) => {
              const cId = community.id ?? community._id;
              const isJoining = joiningId === cId;
              const isSelected = selectedId === cId;
              const topic = community.topic || community.category || "Others";
              const topicStyle = topicColors[topic] || topicColors.Others;
              const createdRaw = community.created_at ?? community.createdAt;
              const created = createdRaw
                ? new Date(createdRaw).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : null;

              return (
                <div
                  key={cId}
                  onClick={() => handleSelect(community)}
                  className={`bg-white rounded-2xl border overflow-hidden hover:shadow-lg hover:shadow-black/5 transition-all cursor-pointer ${
                    isSelected
                      ? "border-primary ring-2 ring-primary/20"
                      : "border-border"
                  }`}
                >
                  {/* Content */}
                  <div className="p-4">
                    <div className="flex items-start gap-3 mb-3">
                      {/* Avatar */}
                      {community.avatar_url ||
                      community.image ||
                      community.picture ? (
                        <img
                          src={
                            community.avatar_url ||
                            community.image ||
                            community.picture
                          }
                          alt={community.name}
                          className="w-11 h-11 rounded-xl object-cover flex-shrink-0"
                        />
                      ) : (
                        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary to-violet-500 flex items-center justify-center text-white text-[13px] font-bold flex-shrink-0">
                          {getInitials(community.name)}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <h3 className="font-heading font-semibold text-[14px] text-text-primary truncate">
                          {community.name}
                        </h3>
                        <span
                          className={`inline-block mt-1 px-2 py-0.5 rounded-md text-[10px] font-semibold ${topicStyle}`}
                        >
                          {topic}
                        </span>
                      </div>
                    </div>

                    <p className="text-[12px] text-text-secondary leading-relaxed mb-3 line-clamp-2">
                      {community.description || "No description"}
                    </p>

                    {/* Stats row */}
                    <div className="flex items-center gap-3 mb-3">
                      {(community.total_members ?? community.memberCount) !=
                        null && (
                        <div className="flex items-center gap-1">
                          <Users
                            size={12}
                            className="text-text-muted"
                            strokeWidth={1.8}
                          />
                          <span className="text-[11px] text-text-muted font-medium">
                            {community.total_members ?? community.memberCount}
                          </span>
                        </div>
                      )}
                      {(community.online_members ?? community.onlineCount) !=
                        null && (
                        <div className="flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-online" />
                          <span className="text-[11px] text-text-muted font-medium">
                            {community.online_members ?? community.onlineCount}{" "}
                            online
                          </span>
                        </div>
                      )}
                      {created && (
                        <div className="flex items-center gap-1">
                          <CalendarDays
                            size={11}
                            className="text-text-muted"
                            strokeWidth={1.8}
                          />
                          <span className="text-[10.5px] text-text-muted font-medium">
                            {created}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Join Button */}
                    {community.joined ? (
                      <button
                        disabled
                        className="w-full py-2.5 rounded-xl bg-[#f0f1f4] text-text-muted text-[12.5px] font-semibold cursor-default"
                      >
                        Joined
                      </button>
                    ) : (
                      <button
                        onClick={(e) => handleJoin(e, cId)}
                        disabled={isJoining}
                        className="w-full py-2.5 rounded-xl bg-primary text-white text-[12.5px] font-semibold hover:bg-primary-dark transition-colors cursor-pointer disabled:opacity-50"
                      >
                        {isJoining ? (
                          <Loader2 size={16} className="animate-spin mx-auto" />
                        ) : (
                          "Join Community"
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-text-muted">
            <Search size={36} strokeWidth={1.2} className="mb-3 opacity-40" />
            <p className="text-[14px] font-medium text-text-secondary">
              No communities found
            </p>
            <p className="text-[12.5px] mt-1">
              Try a different search or category
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
