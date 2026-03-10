import { ShieldAlert, Play, Pause, Trash2 } from "lucide-react";
import { useAudioPlayer } from "../hooks/useAudioPlayer";

/**
 * MessageItem renders a single chat message.
 *
 * Props:
 *  - message: {
 *      id, author, avatar, avatarColor, timestamp, content,
 *      sent?: boolean, canDelete?: boolean,
 *      reactions?: { emoji: string, count: number }[],
 *      image?: string,
 *      voice?: { duration: string, audio_url?: string },
 *      isModerated?: boolean,
 *      moderationFeedback?: string
 *    }
 *  - onDelete?: (messageId) => void
 */
export default function MessageItem({ message, onDelete }) {
  const {
    id,
    author,
    avatar,
    avatarColor,
    timestamp,
    content,
    sent,
    canDelete,
    reactions,
    image,
    voice,
    isModerated,
    moderationFeedback,
  } = message;

  // Audio player hook for voice messages - always call it, pass empty string if no URL
  const audioPlayer = useAudioPlayer(voice?.audio_url || "");

  // ── Moderated state ──
  if (isModerated) {
    return (
      <div className="flex gap-3 px-5 mb-4">
        <div
          className={`w-9 h-9 rounded-full ${avatarColor} flex-shrink-0 flex items-center justify-center text-white text-[11px] font-bold mt-1`}
        >
          {avatar}
        </div>
        <div className="flex-1 min-w-0">
          <span className="font-heading font-semibold text-[13px] text-text-primary">
            {author}
          </span>
          <div className="mt-1.5 flex items-start gap-2.5 p-3.5 rounded-2xl bg-warning-bg border border-warning-border max-w-md">
            <ShieldAlert
              size={18}
              className="text-danger flex-shrink-0 mt-0.5"
            />
            <div>
              <p className="text-[13px] font-semibold text-danger">
                Message blocked: Policy violation detected.
              </p>
              {moderationFeedback && (
                <p className="text-xs text-text-secondary mt-0.5">
                  {moderationFeedback}
                </p>
              )}
            </div>
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">
            {timestamp}
          </span>
        </div>
      </div>
    );
  }

  // ── Sent message (right-aligned, primary color bubble) ──
  if (sent) {
    return (
      <div className="flex justify-end px-5 mb-4 group">
        <div className="max-w-md relative">
          {canDelete && onDelete && (
            <button
              onClick={() => onDelete(id)}
              className="absolute -left-8 top-1/2 -translate-y-1/2 w-6 h-6 rounded-lg flex items-center justify-center text-text-muted hover:text-danger hover:bg-danger/10 opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
              title="Delete message"
            >
              <Trash2 size={13} strokeWidth={1.8} />
            </button>
          )}
          <div className="flex justify-end mb-1">
            <span className="font-heading font-semibold text-[12px] text-primary">
              {author}
            </span>
          </div>
          {/* Voice message - show audio player */}
          {voice && (
            <div className="mt-1.5 flex items-center gap-3 bg-primary rounded-2xl rounded-br-md px-4 py-3 max-w-xs shadow-sm">
              {voice.audio_url ? (
                <button
                  onClick={audioPlayer.togglePlayPause}
                  className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0 cursor-pointer shadow-sm hover:bg-white/30 transition-colors"
                >
                  {audioPlayer.isPlaying ? (
                    <Pause size={16} className="text-white" fill="white" />
                  ) : (
                    <Play
                      size={16}
                      className="text-white ml-0.5"
                      fill="white"
                    />
                  )}
                </button>
              ) : (
                <button className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0 cursor-not-allowed opacity-50">
                  <Play size={16} className="text-white ml-0.5" fill="white" />
                </button>
              )}
              {/* Waveform mock */}
              <div className="flex items-center gap-[3px] flex-1">
                {[
                  3, 5, 8, 4, 7, 10, 6, 9, 3, 5, 8, 11, 6, 4, 7, 9, 5, 3, 6, 8,
                  4, 7, 5, 3,
                ].map((h, i) => {
                  const playbackProgress =
                    voice.audio_url && audioPlayer.duration > 0
                      ? audioPlayer.currentTime / audioPlayer.duration
                      : 0;
                  return (
                    <div
                      key={i}
                      className={`w-[3px] rounded-full ${
                        i < Math.ceil(playbackProgress * 24)
                          ? "bg-white"
                          : "bg-white/40"
                      }`}
                      style={{ height: `${h * 2.5}px` }}
                    />
                  );
                })}
              </div>
              <span className="text-[12px] text-white font-mono font-medium flex-shrink-0">
                {voice.audio_url && audioPlayer.duration > 0
                  ? `${Math.floor(audioPlayer.currentTime)}s / ${Math.floor(audioPlayer.duration)}s`
                  : voice.duration}
              </span>
            </div>
          )}

          {/* Text message */}
          {content && (
            <div className="bg-primary rounded-2xl rounded-br-md px-4 py-2.5 shadow-sm">
              <p className="text-[13px] text-white leading-relaxed">
                {content}
              </p>
            </div>
          )}
          <div className="flex justify-end mt-1">
            <span className="text-[11px] text-text-muted">{timestamp}</span>
          </div>
        </div>
      </div>
    );
  }

  // ── Received message ──
  return (
    <div className="flex gap-3 px-5 mb-4 group">
      {/* Avatar */}
      <div
        className={`w-9 h-9 rounded-full ${avatarColor} flex-shrink-0 flex items-center justify-center text-white text-[11px] font-bold mt-1`}
      >
        {avatar}
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <span className="font-heading font-semibold text-[13px] text-text-primary">
          {author}
        </span>

        {/* Text bubble */}
        {content && (
          <div className="mt-1">
            <div className="bg-bubble-received rounded-2xl rounded-tl-md px-4 py-2.5 max-w-md inline-block">
              <p className="text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap">
                {content}
              </p>
            </div>
          </div>
        )}

        {/* Image message */}
        {image && (
          <div className="mt-1.5 max-w-xs rounded-2xl overflow-hidden shadow-sm">
            <img
              src={image}
              alt="shared"
              className="w-full h-44 object-cover"
              loading="lazy"
            />
          </div>
        )}

        {/* Voice message */}
        {voice && (
          <div className="mt-1.5 flex items-center gap-3 bg-bubble-received rounded-2xl rounded-tl-md px-4 py-3 max-w-xs">
            {voice.audio_url ? (
              <button
                onClick={audioPlayer.togglePlayPause}
                className="w-9 h-9 rounded-full bg-primary flex items-center justify-center flex-shrink-0 cursor-pointer shadow-sm shadow-primary/20 hover:bg-primary-dark transition-colors"
              >
                {audioPlayer.isPlaying ? (
                  <Pause size={16} className="text-white" fill="white" />
                ) : (
                  <Play size={16} className="text-white ml-0.5" fill="white" />
                )}
              </button>
            ) : (
              <button className="w-9 h-9 rounded-full bg-primary flex items-center justify-center flex-shrink-0 cursor-not-allowed shadow-sm shadow-primary/20 opacity-50">
                <Play size={16} className="text-white ml-0.5" fill="white" />
              </button>
            )}
            {/* Waveform mock */}
            <div className="flex items-center gap-[3px] flex-1">
              {[
                3, 5, 8, 4, 7, 10, 6, 9, 3, 5, 8, 11, 6, 4, 7, 9, 5, 3, 6, 8, 4,
                7, 5, 3,
              ].map((h, i) => {
                const playbackProgress =
                  voice.audio_url && audioPlayer.duration > 0
                    ? audioPlayer.currentTime / audioPlayer.duration
                    : 0;
                return (
                  <div
                    key={i}
                    className={`w-[3px] rounded-full ${
                      i < Math.ceil(playbackProgress * 24)
                        ? "bg-primary"
                        : "bg-text-muted/40"
                    }`}
                    style={{ height: `${h * 2.5}px` }}
                  />
                );
              })}
            </div>
            <span className="text-[12px] text-text-muted font-mono font-medium flex-shrink-0">
              {voice.audio_url && audioPlayer.duration > 0
                ? `${Math.floor(audioPlayer.currentTime)}s / ${Math.floor(audioPlayer.duration)}s`
                : voice.duration}
            </span>
          </div>
        )}

        {/* Reactions */}
        {reactions && reactions.length > 0 && (
          <div className="flex gap-1.5 mt-1.5">
            {reactions.map((r, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 text-xs bg-[#f0f1f4] px-2 py-0.5 rounded-full"
              >
                <span>{r.emoji}</span>
                <span className="text-text-muted font-medium">{r.count}</span>
              </span>
            ))}
          </div>
        )}

        {/* Timestamp + delete */}
        <div className="mt-1 flex items-center gap-2">
          <span className="text-[11px] text-text-muted">{timestamp}</span>
          {canDelete && onDelete && (
            <button
              onClick={() => onDelete(id)}
              className="w-5 h-5 rounded-md flex items-center justify-center text-text-muted hover:text-danger hover:bg-danger/10 opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
              title="Delete message"
            >
              <Trash2 size={12} strokeWidth={1.8} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
