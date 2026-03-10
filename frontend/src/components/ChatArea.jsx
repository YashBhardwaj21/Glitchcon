import { useState, useEffect, useRef } from "react";
import {
  Search,
  Phone,
  MoreHorizontal,
  Paperclip,
  Mic,
  Send,
  Loader2,
  Trash2,
  LogOut,
  Pencil,
  X,
  ShieldAlert,
  Info,
  Square,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getMessages, sendMessage as apiSend, sendAudioMessage } from "../api";
import { connectSocket } from "../socket";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";
import MessageItem from "./MessageItem";

export default function ChatArea({
  community,
  onEditCommunity,
  onDeleteCommunity,
  onLeaveCommunity,
  onDeleteMessage,
}) {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editWords, setEditWords] = useState([]);
  const [editWordInput, setEditWordInput] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState(null);
  const [blockedReason, setBlockedReason] = useState(null);
  const {
    isRecording,
    isTranscribing,
    startRecording,
    stopRecording,
    transcribeAudio,
    audioChunksRef,
  } = useVoiceRecorder();
  const menuRef = useRef(null);
  const bottomRef = useRef(null);

  /* Close menu on outside click */
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target))
        setShowMenu(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  /* Fetch messages + WebSocket lifecycle (mirrors Chat.jsx pattern) */
  useEffect(() => {
    if (!community?.id || !token) {
      setMessages([]);
      return;
    }
    const communityId = community.id;

    setMessages([]);
    setLoadingMessages(true);
    getMessages(token, communityId)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.messages ?? []);
        setMessages(list);
      })
      .catch(() => setMessages([]))
      .finally(() => setLoadingMessages(false));

    const s = connectSocket(token);
    s.on("connect", () => {
      s.emit("join_room", { communityId });
    });
    s.on("receive_message", (msg) => {
      setMessages((prev) => [...prev, msg]);
    });
    s.on("message_deleted", ({ messageId }) => {
      setMessages((prev) => prev.filter((m) => (m.id ?? m._id) !== messageId));
    });

    return () => s.disconnect();
  }, [community?.id, token]);

  /* Auto-scroll when messages change */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* Send message — let the socket receive_message listener update the UI */
  const handleSend = async () => {
    const text = input.trim();
    if (!text || !community?.id || sending) return;
    setSending(true);
    try {
      await apiSend(token, community.id, text);
      setInput("");
    } catch (err) {
      if (err?.status === 422 && err?.blocked) {
        setBlockedReason(
          err.reason || "Your message was blocked by moderation.",
        );
        setTimeout(() => setBlockedReason(null), 10000);
      }
    } finally {
      setSending(false);
    }
  };

  /* Handle voice recording — click to toggle recording on/off */
  const handleVoiceClick = async () => {
    if (isRecording) {
      // Stop recording and send as AUDIO message (NOT text)
      if (!community?.id || sending || isTranscribing) return;

      setSending(true);
      try {
        stopRecording();

        // Wait for recording to fully stop
        await new Promise((resolve) => {
          setTimeout(resolve, 500);
        });

        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, {
            type: "audio/webm",
          });

          // Transcribe audio
          const transcription = await transcribeAudio(audioBlob);
          console.log("[Voice] Transcription result:", transcription);

          // Check if transcription succeeded
          if (transcription && transcription.trim()) {
            // Send as AUDIO message with type: "audio", transcription, and audio file
            // DO NOT send as text message
            await sendAudioMessage(
              token,
              community.id,
              audioBlob,
              transcription,
            );
          }
        }
      } catch (err) {
        if (err?.status === 422 && err?.blocked) {
          setBlockedReason(
            err.reason || "Your message was blocked by moderation.",
          );
          setTimeout(() => setBlockedReason(null), 10000);
        } else {
          console.error("Voice message error:", err);
        }
      } finally {
        setSending(false);
      }
    } else {
      // Start recording
      try {
        await startRecording();
      } catch (err) {
        console.error("Failed to start recording:", err);
      }
    }
  };

  /* Handle Enter key in input */
  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !sending && input.trim()) {
      e.preventDefault();
      handleSend();
    }
  };

  /* Map API message to the shape MessageItem expects */
  const mapMsg = (m) => {
    const authorName = m.sender?.name ?? "Unknown";
    const senderId = String(m.sender?.id ?? m.sender?._id ?? "");
    const currentUserId = String(user?.id ?? user?._id ?? "");
    const isSent = senderId && currentUserId && senderId === currentUserId;

    // Check if current user is admin or owner of this community
    const role = (community?.role ?? community?.userRole ?? "").toLowerCase();
    const isOwner =
      community?.isOwner === true ||
      role === "owner" ||
      community?.owner_id === (user?.id ?? user?._id);
    const isAdmin = role === "admin" || isOwner;

    const mappedMsg = {
      id: m.id ?? m._id,
      author: authorName,
      avatar: authorName
        .split(" ")
        .map((w) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2),
      avatarColor: "bg-gradient-to-br from-indigo-400 to-violet-500",
      timestamp:
        (m.createdAt ?? m.created_at)
          ? new Date(m.createdAt ?? m.created_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })
          : "",
      content: m.content ?? "",
      sent: isSent,
      canDelete: isSent || isAdmin,
    };

    // Handle audio messages - show audio player instead of text content
    if (m.type === "audio" && m.audio_url) {
      mappedMsg.voice = {
        duration: m.duration ? `${Math.floor(m.duration)}s` : "0s",
        audio_url: m.audio_url,
      };
      // Clear content for audio messages - don't show transcription as text
      mappedMsg.content = "";
    }

    return mappedMsg;
  };

  if (!community) {
    return (
      <div className="flex flex-col flex-1 items-center justify-center min-w-0 overflow-hidden bg-card">
        <p className="text-text-muted text-[14px]">
          Select a community to start chatting
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          {community?.avatar_url || community?.image || community?.picture ? (
            <img
              src={community.avatar_url || community.image || community.picture}
              alt={community.name}
              className="w-9 h-9 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-violet-500 flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0">
              {(community.name ?? "")
                .split(" ")
                .map((w) => w[0])
                .join("")
                .toUpperCase()
                .slice(0, 2)}
            </div>
          )}
          <div>
            <h2 className="font-heading font-semibold text-text-primary text-[17px] leading-tight">
              {community.name}
            </h2>
            <div className="flex items-center gap-3 mt-0.5">
              <p className="text-[12px] text-text-muted">
                {community.description || "Community chat"}
              </p>
              {community.total_members != null && (
                <span className="text-[11px] text-text-muted font-medium">
                  · {community.total_members} members
                </span>
              )}
              {community.online_members != null &&
                community.online_members > 0 && (
                  <span className="flex items-center gap-1 text-[11px] text-text-muted font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-online" />
                    {community.online_members} online
                  </span>
                )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[Search, Phone].map((Icon, i) => (
            <button
              key={i}
              className="w-9 h-9 rounded-xl flex items-center justify-center text-text-muted hover:bg-[#f0f1f4] hover:text-text-primary transition-colors cursor-pointer"
            >
              <Icon size={18} strokeWidth={1.7} />
            </button>
          ))}
          {/* 3-dot menu — visible to admins/owners or any member (for leave) */}
          {community && (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowMenu((v) => !v)}
                className="w-9 h-9 rounded-xl flex items-center justify-center text-text-muted hover:bg-[#f0f1f4] hover:text-text-primary transition-colors cursor-pointer"
              >
                <MoreHorizontal size={18} strokeWidth={1.7} />
              </button>
              {showMenu &&
                (() => {
                  const role = (
                    community.role ??
                    community.userRole ??
                    ""
                  ).toLowerCase();
                  const isOwner =
                    community.isOwner === true ||
                    role === "owner" ||
                    community.owner === (user?.id ?? user?._id) ||
                    community.ownerId === (user?.id ?? user?._id) ||
                    community.owner_id === (user?.id ?? user?._id) ||
                    community.createdBy === (user?.id ?? user?._id);
                  console.log(
                    "[menu] community:",
                    community,
                    "isOwner:",
                    isOwner,
                    "role:",
                    role,
                  );
                  return (
                    <div className="absolute right-0 top-11 w-52 bg-card rounded-2xl shadow-xl shadow-black/12 border border-border py-1.5 z-50">
                      {(isOwner || role === "admin") && (
                        <button
                          onClick={() => {
                            setShowMenu(false);
                            setEditName(community.name || "");
                            setEditDesc(community.description || "");
                            setEditWords(community.restricted_words ?? []);
                            setEditWordInput("");
                            setEditError(null);
                            setShowEditModal(true);
                          }}
                          className="flex items-center gap-2.5 w-full px-4 py-2.5 text-left text-text-secondary text-[13px] font-medium hover:bg-[#f0f1f4] transition-colors cursor-pointer"
                        >
                          <Pencil size={15} strokeWidth={1.8} />
                          Edit Community
                        </button>
                      )}
                      {isOwner && (
                        <button
                          onClick={() => {
                            setShowMenu(false);
                            onDeleteCommunity?.(community.id ?? community._id);
                          }}
                          className="flex items-center gap-2.5 w-full px-4 py-2.5 text-left text-danger text-[13px] font-medium hover:bg-danger/8 transition-colors cursor-pointer"
                        >
                          <Trash2 size={15} strokeWidth={1.8} />
                          Delete Community
                        </button>
                      )}
                      <button
                        onClick={() => {
                          if (isOwner) return;
                          setShowMenu(false);
                          onLeaveCommunity?.(community.id ?? community._id);
                        }}
                        disabled={isOwner}
                        className={`flex items-center gap-2.5 w-full px-4 py-2.5 text-left text-[13px] font-medium transition-colors ${
                          isOwner
                            ? "text-text-muted/40 cursor-not-allowed"
                            : "text-text-secondary hover:bg-[#f0f1f4] cursor-pointer"
                        }`}
                        title={
                          isOwner
                            ? "Owner cannot leave. Delete the community instead."
                            : undefined
                        }
                      >
                        <LogOut size={15} strokeWidth={1.8} />
                        Leave Community
                      </button>
                    </div>
                  );
                })()}
            </div>
          )}
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto py-4">
        {loadingMessages ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <Loader2 size={28} className="animate-spin text-primary" />
            <p className="text-[13px] text-text-muted font-medium">
              Loading messages…
            </p>
          </div>
        ) : (
          <>
            {/* Today Divider */}
            <div className="flex items-center gap-4 px-5 mb-5">
              <div className="flex-1 h-px bg-border" />
              <span className="font-heading text-[11px] font-medium text-text-muted bg-card px-3 py-1 rounded-full border border-border">
                Today
              </span>
              <div className="flex-1 h-px bg-border" />
            </div>

            {messages.length === 0 && (
              <p className="text-center text-[13px] text-text-muted py-12">
                No messages yet — say hello!
              </p>
            )}

            {messages.map((m) => (
              <MessageItem
                key={m.id ?? m._id}
                message={mapMsg(m)}
                onDelete={(msgId) => {
                  onDeleteMessage?.(community.id ?? community._id, msgId);
                  setMessages((prev) =>
                    prev.filter((msg) => (msg.id ?? msg._id) !== msgId),
                  );
                }}
              />
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Moderation nudge — above input, pushes messages up */}
      {blockedReason && (
        <div className="px-5 pb-2 flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 flex items-center justify-center text-white flex-shrink-0">
            <Info size={14} strokeWidth={2} />
          </div>
          <div className="flex-1 min-w-0 bg-primary/8 border border-primary/15 rounded-2xl px-4 py-2.5">
            <p className="text-[12.5px] text-text-primary leading-relaxed">
              {blockedReason}
            </p>
          </div>
          <button
            onClick={() => setBlockedReason(null)}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-primary hover:bg-primary/8 transition-colors cursor-pointer flex-shrink-0 mt-0.5"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>
      )}

      {/* Input Area */}
      <div className="px-5 pb-4 pt-1">
        <div className="flex items-center gap-3 bg-[#f0f1f4] rounded-2xl px-4 py-3">
          <button className="text-text-muted hover:text-primary transition-colors cursor-pointer">
            <Paperclip size={20} strokeWidth={1.7} />
          </button>
          <input
            type="text"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            className="flex-1 text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium"
          />
          <button
            onClick={handleVoiceClick}
            disabled={sending || isTranscribing}
            className={`text-text-muted transition-colors cursor-pointer flex items-center gap-1.5 ${
              isRecording
                ? "text-red-500 hover:text-red-400"
                : "hover:text-primary"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <Mic size={20} strokeWidth={1.7} />
            {isRecording && (
              <span className="text-[11px] text-red-500 font-semibold">
                Recording...
              </span>
            )}
            {isTranscribing && (
              <span className="text-[11px] text-primary font-semibold">
                Transcribing...
              </span>
            )}
          </button>
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-white cursor-pointer hover:bg-primary-dark transition-colors shadow-sm shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} strokeWidth={2} className="ml-0.5" />
            )}
          </button>
        </div>
      </div>

      {/* Edit Community Modal */}
      {showEditModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card rounded-3xl p-6 w-[400px] shadow-2xl shadow-black/20 mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-heading font-semibold text-[17px] text-text-primary">
                Edit Community
              </h3>
              <button
                onClick={() => setShowEditModal(false)}
                className="w-8 h-8 rounded-xl flex items-center justify-center text-text-muted hover:bg-[#f0f1f4] transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {editError && (
              <div className="mb-4 px-4 py-3 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] font-medium">
                {editError}
              </div>
            )}

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!editName.trim() || editSaving) return;
                setEditSaving(true);
                setEditError(null);
                try {
                  await onEditCommunity(community.id ?? community._id, {
                    name: editName.trim(),
                    description: editDesc.trim(),
                    restricted_words: editWords,
                  });
                  setShowEditModal(false);
                } catch (err) {
                  setEditError(err.message || "Failed to update community");
                } finally {
                  setEditSaving(false);
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-[12.5px] font-semibold text-text-secondary mb-1.5 ml-1">
                  Community Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
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
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
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
                  {editWords.map((w) => (
                    <span
                      key={w}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-primary/12 text-primary text-[12px] font-semibold"
                    >
                      {w}
                      <button
                        type="button"
                        onClick={() =>
                          setEditWords((prev) => prev.filter((x) => x !== w))
                        }
                        className="w-4 h-4 rounded-full flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer"
                      >
                        <X size={10} strokeWidth={2.5} />
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={editWordInput}
                    onChange={(e) => setEditWordInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        const w = editWordInput.trim().toLowerCase();
                        if (w && !editWords.includes(w)) {
                          setEditWords((prev) => [...prev, w]);
                        }
                        setEditWordInput("");
                      }
                      if (
                        e.key === "Backspace" &&
                        !editWordInput &&
                        editWords.length
                      ) {
                        setEditWords((prev) => prev.slice(0, -1));
                      }
                    }}
                    placeholder={
                      editWords.length === 0 ? "Type a word & press Enter" : ""
                    }
                    className="flex-1 min-w-[100px] text-[13px] text-text-primary placeholder:text-text-muted outline-none bg-transparent font-medium py-0.5"
                  />
                </div>
                <p className="text-[11px] text-text-muted mt-1 ml-1">
                  Press Enter to add. Backspace to remove the last one.
                </p>
              </div>
              <button
                type="submit"
                disabled={editSaving || !editName.trim()}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-white font-semibold text-[14px] hover:bg-primary-dark active:scale-[0.98] transition-all shadow-lg shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {editSaving ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  "Save Changes"
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
