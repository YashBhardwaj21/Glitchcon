import { useState } from "react";
import {
  Search,
  Pin,
  Phone,
  MoreHorizontal,
  Paperclip,
  Mic,
  Send,
} from "lucide-react";

const chats = [
  {
    id: 1,
    name: "Mom 💛",
    avatar: "MO",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    preview: "Don't forget dinner on Sunday!",
    time: "11:02",
    unread: 1,
    pinned: true,
    active: true,
  },
  {
    id: 2,
    name: "Design chat",
    avatar: "DC",
    avatarColor: "bg-gradient-to-br from-indigo-400 to-violet-500",
    preview: "Nolan: Check this out guys ✌️",
    time: "10:25",
    unread: 0,
    pinned: true,
    active: false,
  },
  {
    id: 3,
    name: "Jake Thompson",
    avatar: "JT",
    avatarColor: "bg-gradient-to-br from-sky-400 to-blue-500",
    preview: "Movie tonight? 🎬",
    time: "10:10",
    unread: 2,
    pinned: false,
    active: false,
  },
  {
    id: 4,
    name: "Dev Team",
    avatar: "DT",
    avatarColor: "bg-gradient-to-br from-emerald-400 to-teal-500",
    preview: "Build passed ✅ deploying now",
    time: "09:12",
    unread: 0,
    pinned: true,
    active: false,
  },
  {
    id: 5,
    name: "Emily Chen",
    avatar: "EC",
    avatarColor: "bg-gradient-to-br from-amber-400 to-orange-500",
    preview: "Happy birthday!! 🎂🎉",
    time: "Yesterday",
    unread: 0,
    pinned: false,
    active: false,
  },
  {
    id: 6,
    name: "Sarah Miller",
    avatar: "SM",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    preview: "Let me know about the deadline...",
    time: "Yesterday",
    unread: 3,
    pinned: false,
    active: false,
  },
  {
    id: 7,
    name: "Gym Buddies 💪",
    avatar: "GB",
    avatarColor: "bg-gradient-to-br from-lime-400 to-green-500",
    preview: "Leg day tomorrow, no excuses",
    time: "Yesterday",
    unread: 0,
    pinned: false,
    active: false,
  },
  {
    id: 8,
    name: "Alex Johnson",
    avatar: "AJ",
    avatarColor: "bg-gradient-to-br from-amber-400 to-orange-500",
    preview: "Can you review the PR?",
    time: "Mon",
    unread: 0,
    pinned: false,
    active: false,
  },
  {
    id: 9,
    name: "Landlord",
    avatar: "LL",
    avatarColor: "bg-gradient-to-br from-gray-400 to-slate-500",
    preview: "Maintenance scheduled for Tuesday",
    time: "Mon",
    unread: 0,
    pinned: false,
    active: false,
  },
];

const activeChat = chats[0];

const messages = [
  {
    id: 1,
    author: "Mom",
    avatar: "MO",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    content:
      "Hey sweetie! Just making sure you remember dinner on Sunday at 6. Dad is grilling 🍖",
    time: "10:45",
    sent: false,
  },
  {
    id: 2,
    author: "You",
    content:
      "Of course! I'll bring dessert. Should I come earlier to help set up?",
    time: "10:50",
    sent: true,
  },
  {
    id: 3,
    author: "Mom",
    avatar: "MO",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    content:
      "That would be lovely! Come at 4 if you can. Also your sister is bringing the kids 👶",
    time: "10:58",
    sent: false,
  },
  {
    id: 4,
    author: "Mom",
    avatar: "MO",
    avatarColor: "bg-gradient-to-br from-rose-400 to-pink-500",
    content: "Don't forget dinner on Sunday!",
    time: "11:02",
    sent: false,
  },
];

export default function AllChatsView() {
  const [selectedChat, setSelectedChat] = useState(activeChat.id);

  return (
    <>
      {/* Merged chat card: list + conversation */}
      <div className="flex flex-1 min-w-0 bg-card rounded-3xl overflow-hidden">
        {/* Chat List */}
        <div className="flex flex-col w-[280px] min-w-[280px] border-r border-border-chat bg-chat-list-bg overflow-hidden">
          <div className="p-4 pb-2">
            <h2 className="font-heading font-semibold text-[15px] text-text-primary mb-3">
              Direct Messages
            </h2>
            <div className="flex items-center gap-2.5 bg-[#f0f1f4] rounded-2xl px-4 py-2.5">
              <Search size={16} className="text-text-muted flex-shrink-0" />
              <input
                type="text"
                placeholder="Search messages"
                className="flex-1 text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-3">
            {chats.map((chat) => (
              <button
                key={chat.id}
                onClick={() => setSelectedChat(chat.id)}
                className={`flex items-center gap-3 w-full px-3 py-3 rounded-2xl text-left cursor-pointer transition-all ${
                  chat.id === selectedChat
                    ? "bg-active-chat"
                    : "hover:bg-chat-item-hover"
                }`}
              >
                <div
                  className={`w-11 h-11 rounded-full ${chat.avatarColor} flex items-center justify-center text-white text-[12px] font-bold flex-shrink-0`}
                >
                  {chat.avatar}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="font-heading font-semibold text-[13.5px] text-text-primary truncate">
                      {chat.name}
                    </span>
                    <span className="text-[11px] text-text-muted ml-2 flex-shrink-0">
                      {chat.time}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-[12.5px] text-text-secondary truncate pr-2">
                      {chat.preview}
                    </p>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {chat.pinned && (
                        <Pin
                          size={12}
                          className="text-text-muted rotate-45"
                          strokeWidth={2}
                        />
                      )}
                      {chat.unread > 0 && (
                        <span className="min-w-[20px] h-[20px] rounded-full bg-badge text-white text-[10px] font-bold flex items-center justify-center px-1.5">
                          {chat.unread}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <div>
              <h2 className="font-heading font-semibold text-[15px] text-text-primary">
                {activeChat.name}
              </h2>
              <p className="text-[12px] text-text-secondary mt-0.5">Personal</p>
            </div>
            <div className="flex items-center gap-1">
              <button className="w-9 h-9 rounded-xl flex items-center justify-center text-text-muted hover:bg-hover transition-colors cursor-pointer">
                <Phone size={17} strokeWidth={1.6} />
              </button>
              <button className="w-9 h-9 rounded-xl flex items-center justify-center text-text-muted hover:bg-hover transition-colors cursor-pointer">
                <MoreHorizontal size={17} strokeWidth={1.6} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${
                  msg.sent ? "justify-end" : "justify-start"
                }`}
              >
                {!msg.sent && (
                  <div
                    className={`w-8 h-8 rounded-full ${msg.avatarColor} flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 mt-1`}
                  >
                    {msg.avatar}
                  </div>
                )}
                <div className={`max-w-[65%] ${msg.sent ? "items-end" : ""}`}>
                  <div
                    className={`px-4 py-2.5 text-[13.5px] leading-relaxed ${
                      msg.sent
                        ? "bg-primary text-white rounded-2xl rounded-br-md"
                        : "bg-bubble-received text-text-primary rounded-2xl rounded-tl-md"
                    }`}
                  >
                    {msg.content}
                  </div>
                  <p
                    className={`text-[10.5px] text-text-muted mt-1 ${
                      msg.sent ? "text-right" : ""
                    }`}
                  >
                    {msg.time}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Input */}
          <div className="px-5 py-4 border-t border-border">
            <div className="flex items-center gap-3 bg-[#f0f1f4] rounded-2xl px-4 py-3">
              <button className="text-text-muted hover:text-text-secondary transition-colors cursor-pointer">
                <Paperclip size={18} strokeWidth={1.6} />
              </button>
              <input
                type="text"
                placeholder="Type a message..."
                className="flex-1 text-[13.5px] text-text-primary placeholder:text-text-muted outline-none bg-transparent"
              />
              <button className="text-text-muted hover:text-text-secondary transition-colors cursor-pointer">
                <Mic size={18} strokeWidth={1.6} />
              </button>
              <button className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-white hover:bg-primary-dark transition-colors cursor-pointer">
                <Send size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
