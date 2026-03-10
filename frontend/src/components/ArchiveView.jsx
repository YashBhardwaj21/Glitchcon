import { Archive, ArchiveRestore, Trash2, Search, BellOff } from "lucide-react";

const archivedChats = [
  {
    id: 1,
    name: "Old Project Alpha",
    avatar: "PA",
    avatarColor: "bg-gradient-to-br from-gray-400 to-slate-500",
    lastMessage: "Thanks everyone, project wrapped up!",
    archivedDate: "Feb 28, 2026",
    muted: true,
  },
  {
    id: 2,
    name: "Hackathon 2025",
    avatar: "H5",
    avatarColor: "bg-gradient-to-br from-violet-400 to-purple-500",
    lastMessage: "GG everyone! Great experience 🎉",
    archivedDate: "Jan 15, 2026",
    muted: true,
  },
  {
    id: 3,
    name: "Apartment Search",
    avatar: "AS",
    avatarColor: "bg-gradient-to-br from-amber-400 to-orange-500",
    lastMessage: "Found a place! Signing the lease tomorrow",
    archivedDate: "Dec 20, 2025",
    muted: false,
  },
  {
    id: 4,
    name: "Wedding Planning",
    avatar: "WP",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    lastMessage: "All done! See you at the venue ❤️",
    archivedDate: "Nov 5, 2025",
    muted: true,
  },
  {
    id: 5,
    name: "CS 301 Study Group",
    avatar: "CS",
    avatarColor: "bg-gradient-to-br from-sky-400 to-blue-500",
    lastMessage: "Final exam is over 🙌 good luck everyone",
    archivedDate: "Oct 18, 2025",
    muted: false,
  },
];

export default function ArchiveView() {
  return (
    <div className="flex flex-col flex-1 min-w-0 bg-card rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-3">
            <Archive size={20} className="text-primary" strokeWidth={2} />
            <h1 className="font-heading font-semibold text-[18px] text-text-primary">
              Archived Chats
            </h1>
          </div>
          <span className="text-[12.5px] text-text-muted font-medium">
            {archivedChats.length} conversations
          </span>
        </div>
      </div>

      {/* Search */}
      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center gap-2.5 bg-[#f0f1f4] rounded-2xl px-4 py-2.5">
          <Search size={16} className="text-text-muted flex-shrink-0" />
          <input
            type="text"
            placeholder="Search archived chats..."
            className="flex-1 text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
          />
        </div>
      </div>

      {/* Archived List */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {archivedChats.map((chat) => (
          <div
            key={chat.id}
            className="flex items-center gap-3 px-3 py-3.5 rounded-2xl hover:bg-chat-item-hover transition-colors group"
          >
            {/* Avatar */}
            <div
              className={`w-11 h-11 rounded-full ${chat.avatarColor} flex items-center justify-center text-white text-[12px] font-bold flex-shrink-0 opacity-70`}
            >
              {chat.avatar}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="font-heading font-semibold text-[13.5px] text-text-primary truncate">
                  {chat.name}
                </span>
                {chat.muted && (
                  <BellOff
                    size={12}
                    className="text-text-muted flex-shrink-0"
                    strokeWidth={1.8}
                  />
                )}
              </div>
              <p className="text-[12.5px] text-text-secondary truncate">
                {chat.lastMessage}
              </p>
              <p className="text-[11px] text-text-muted mt-0.5">
                Archived {chat.archivedDate}
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                title="Unarchive"
                className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer"
              >
                <ArchiveRestore size={15} strokeWidth={1.8} />
              </button>
              <button
                title="Delete"
                className="w-9 h-9 rounded-xl bg-danger/10 text-danger flex items-center justify-center hover:bg-danger/20 transition-colors cursor-pointer"
              >
                <Trash2 size={15} strokeWidth={1.8} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
