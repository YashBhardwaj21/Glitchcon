import { useState, useRef } from "react";
import {
  Search,
  Plus,
  UserPlus,
  X,
  Loader2,
  Users,
  Camera,
} from "lucide-react";

/* Color palette for auto-generated avatars */
const avatarColors = [
  "bg-gradient-to-br from-indigo-400 to-violet-500",
  "bg-gradient-to-br from-rose-400 to-pink-500",
  "bg-gradient-to-br from-emerald-400 to-teal-500",
  "bg-gradient-to-br from-amber-400 to-orange-500",
  "bg-gradient-to-br from-cyan-400 to-blue-500",
  "bg-gradient-to-br from-fuchsia-400 to-purple-500",
  "bg-gradient-to-br from-lime-400 to-green-500",
  "bg-gradient-to-br from-sky-400 to-blue-500",
];

function getInitials(name = "") {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function pickColor(id = "") {
  let hash = 0;
  for (const ch of String(id)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return avatarColors[hash % avatarColors.length];
}

export default function ChatList({
  communities = [],
  activeCommunity,
  onSelect,
  onCreateCommunity,
  onJoinCommunity,
}) {
  const [showModal, setShowModal] = useState(null); // 'create' | 'join' | null
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [restrictedWords, setRestrictedWords] = useState([]);
  const [wordInput, setWordInput] = useState("");
  const [joinId, setJoinId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [communityAvatar, setCommunityAvatar] = useState(null);
  const [communityAvatarPreview, setCommunityAvatarPreview] = useState(null);
  const communityAvatarRef = useRef(null);

  const addWord = () => {
    const w = wordInput.trim().toLowerCase();
    if (w && !restrictedWords.includes(w)) {
      setRestrictedWords((prev) => [...prev, w]);
    }
    setWordInput("");
  };

  const removeWord = (word) =>
    setRestrictedWords((prev) => prev.filter((w) => w !== word));

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim() || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      await onCreateCommunity(
        newName.trim(),
        newDesc.trim(),
        restrictedWords,
        communityAvatar,
      );
      setNewName("");
      setNewDesc("");
      setRestrictedWords([]);
      setWordInput("");
      setCommunityAvatar(null);
      setCommunityAvatarPreview(null);
      setShowModal(null);
    } catch (err) {
      setCreateError(err.message || "Failed to create community");
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    if (!joinId.trim() || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      await onJoinCommunity(joinId.trim());
      setJoinId("");
      setShowModal(null);
    } catch (err) {
      setCreateError(err.message || "Failed to join community");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col w-[280px] min-w-[280px] border-r border-border-chat bg-chat-list-bg overflow-hidden">
      {/* Search */}
      <div className="p-4 pb-2">
        <div className="flex items-center gap-2.5 bg-[#f0f1f4] rounded-2xl px-4 py-2.5">
          <Search size={16} className="text-text-muted flex-shrink-0" />
          <input
            type="text"
            placeholder="Search"
            className="flex-1 text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-4 pb-2 flex gap-2">
        <button
          onClick={() => setShowModal("create")}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#ece8ff] text-[#7678ed] text-[12.5px] font-semibold hover:bg-[#e0dbff] transition-colors cursor-pointer"
        >
          <Plus size={14} strokeWidth={2.5} />
          Create
        </button>
        <button
          onClick={() => setShowModal("join")}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#ece8ff] text-[#7678ed] text-[12.5px] font-semibold hover:bg-[#e0dbff] transition-colors cursor-pointer"
        >
          <UserPlus size={14} strokeWidth={2} />
          Join
        </button>
      </div>

      {/* Modal Overlay */}
      {showModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card rounded-3xl p-6 w-[360px] shadow-2xl shadow-black/20 mx-4">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-heading font-semibold text-[17px] text-text-primary">
                {showModal === "create" ? "Create Community" : "Join Community"}
              </h3>
              <button
                onClick={() => {
                  setShowModal(null);
                  setCreateError(null);
                }}
                className="w-8 h-8 rounded-xl flex items-center justify-center text-text-muted hover:bg-[#f0f1f4] transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {createError && (
              <div className="mb-4 px-4 py-3 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] font-medium">
                {createError}
              </div>
            )}

            {showModal === "create" ? (
              <form onSubmit={handleCreate} className="space-y-4">
                {/* Community Avatar */}
                <div>
                  <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                    Avatar{" "}
                    <span className="text-text-muted font-normal">
                      (optional)
                    </span>
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      ref={communityAvatarRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        if (file.size > 5 * 1024 * 1024) {
                          setCreateError("Avatar must be under 5 MB");
                          return;
                        }
                        setCommunityAvatar(file);
                        setCommunityAvatarPreview(URL.createObjectURL(file));
                      }}
                      className="hidden"
                    />
                    {communityAvatarPreview ? (
                      <div className="relative">
                        <img
                          src={communityAvatarPreview}
                          alt="Community avatar"
                          className="w-12 h-12 rounded-xl object-cover ring-2 ring-primary/20"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setCommunityAvatar(null);
                            setCommunityAvatarPreview(null);
                            if (communityAvatarRef.current)
                              communityAvatarRef.current.value = "";
                          }}
                          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-danger text-white flex items-center justify-center shadow-md hover:bg-danger/80 transition-colors cursor-pointer"
                        >
                          <X size={10} strokeWidth={3} />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => communityAvatarRef.current?.click()}
                        className="w-12 h-12 rounded-xl bg-[#f0f1f4] flex items-center justify-center text-text-muted hover:bg-[#e6e7eb] hover:text-text-secondary transition-colors cursor-pointer"
                      >
                        <Camera size={18} />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => communityAvatarRef.current?.click()}
                      className="text-[12.5px] font-semibold text-primary hover:underline cursor-pointer"
                    >
                      {communityAvatarPreview ? "Change" : "Upload photo"}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                    Community Name
                  </label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. Design Team"
                    required
                    className="w-full px-4 py-3 rounded-xl bg-[#f0f1f4] text-[14px] text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-primary/30 transition-shadow font-medium"
                  />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                    Description
                  </label>
                  <textarea
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    placeholder="What's this community about?"
                    rows={3}
                    className="w-full px-4 py-3 rounded-xl bg-[#f0f1f4] text-[14px] text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-primary/30 transition-shadow font-medium resize-none"
                  />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                    Restricted Words
                  </label>
                  <div className="flex flex-wrap gap-1.5 min-h-[44px] p-2.5 rounded-xl bg-[#f0f1f4] focus-within:ring-2 focus-within:ring-primary/30 transition-shadow">
                    {restrictedWords.map((w) => (
                      <span
                        key={w}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-primary/12 text-primary text-[12px] font-semibold"
                      >
                        {w}
                        <button
                          type="button"
                          onClick={() => removeWord(w)}
                          className="w-4 h-4 rounded-full flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer"
                        >
                          <X size={10} strokeWidth={2.5} />
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      value={wordInput}
                      onChange={(e) => setWordInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addWord();
                        }
                        if (
                          e.key === "Backspace" &&
                          !wordInput &&
                          restrictedWords.length
                        ) {
                          removeWord(
                            restrictedWords[restrictedWords.length - 1],
                          );
                        }
                      }}
                      placeholder={
                        restrictedWords.length === 0
                          ? "Type a word & press Enter"
                          : ""
                      }
                      className="flex-1 min-w-[100px] text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium py-0.5"
                    />
                  </div>
                  <p className="text-[11px] text-text-muted mt-1 ml-1">
                    Press Enter to add a word. Backspace to remove the last one.
                  </p>
                </div>
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-white font-semibold text-[14px] hover:bg-primary-dark active:scale-[0.98] transition-all shadow-lg shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {creating ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    "Create Community"
                  )}
                </button>
              </form>
            ) : (
              <form onSubmit={handleJoin} className="space-y-4">
                <div>
                  <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                    Community ID
                  </label>
                  <input
                    type="text"
                    value={joinId}
                    onChange={(e) => setJoinId(e.target.value)}
                    placeholder="Paste the community ID"
                    required
                    className="w-full px-4 py-3 rounded-xl bg-[#f0f1f4] text-[14px] text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-primary/30 transition-shadow font-medium"
                  />
                </div>
                <button
                  type="submit"
                  disabled={creating || !joinId.trim()}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-white font-semibold text-[14px] hover:bg-primary-dark active:scale-[0.98] transition-all shadow-lg shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {creating ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    "Join Community"
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {communities.length === 0 && (
          <p className="text-center text-[12.5px] text-text-muted py-8">
            No communities yet
          </p>
        )}
        {communities.map((c) => {
          const isActive = activeCommunity?.id === c.id;
          return (
            <button
              key={c.id}
              onClick={() => onSelect(c)}
              className={`flex items-center gap-3 w-full px-3 py-3 rounded-2xl text-left cursor-pointer transition-all ${
                isActive ? "bg-active-chat" : "hover:bg-chat-item-hover"
              }`}
            >
              {/* Avatar */}
              {c.avatar_url || c.image || c.picture ? (
                <img
                  src={c.avatar_url || c.image || c.picture}
                  alt={c.name}
                  className="w-11 h-11 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div
                  className={`w-11 h-11 rounded-full ${pickColor(c.id)} flex items-center justify-center text-white text-[12px] font-bold flex-shrink-0`}
                >
                  {getInitials(c.name)}
                </div>
              )}

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-heading font-semibold text-[13.5px] text-text-primary truncate">
                    {c.name}
                  </span>
                </div>
                <p className="text-[12px] text-text-secondary truncate pr-2 mb-1">
                  {c.description || "No description"}
                </p>
                <div className="flex items-center gap-3">
                  {c.total_members != null && (
                    <div className="flex items-center gap-1">
                      <Users
                        size={11}
                        className="text-text-muted"
                        strokeWidth={1.8}
                      />
                      <span className="text-[10.5px] text-text-muted font-medium">
                        {c.total_members}
                      </span>
                    </div>
                  )}
                  {c.online_members != null && c.online_members > 0 && (
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-online" />
                      <span className="text-[10.5px] text-text-muted font-medium">
                        {c.online_members} online
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
