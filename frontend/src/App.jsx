import { useState, useEffect, useRef } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import {
  getCommunity,
  getMyCommunities,
  createCommunity,
  updateCommunity,
  joinCommunity,
  deleteCommunity,
  leaveCommunity,
  deleteMessage,
  addAdmin,
  removeAdmin,
} from "./api";
import { getSocket } from "./socket";
import "./App.css";
import LeftNav from "./components/LeftNav";
import ChatList from "./components/ChatList";
import ChatArea from "./components/ChatArea";
import RightSidebar from "./components/RightSidebar";
import AllChatsView from "./components/AllChatsView";
import FriendsView from "./components/FriendsView";
import DiscoverView from "./components/DiscoverView";
import ArchiveView from "./components/ArchiveView";
import AuthPage from "./components/AuthPage";
import LandingPage from "./components/LandingPage";

function Dashboard() {
  const [activeView, setActiveView] = useState("communities");
  const [communities, setCommunities] = useState([]);
  const [activeCommunity, setActiveCommunity] = useState(null);
  const [messages, setMessages] = useState([]);
  const [onlineUserIds, setOnlineUserIds] = useState(new Set());
  const [onlineCount, setOnlineCount] = useState(0);
  const { token, logout } = useAuth();

  /* Fetch user's joined communities on mount */
  useEffect(() => {
    if (!token) return;
    getMyCommunities(token)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.communities ?? []);
        console.log("[communities/me]", JSON.stringify(list[0], null, 2));
        setCommunities(list);
        setActiveCommunity(
          (prev) => prev || (list.length > 0 ? list[0] : null),
        );
      })
      .catch(() => {});
  }, [token]);

  const [discoverCommunity, setDiscoverCommunity] = useState(null);
  const fetchedCommunityRef = useRef(null);

  /* Fetch full community details when active community changes */
  useEffect(() => {
    const cId = activeCommunity?.id ?? activeCommunity?._id;
    if (!cId || !token || fetchedCommunityRef.current === cId) return;
    fetchedCommunityRef.current = cId;
    let cancelled = false;
    getCommunity(token, cId)
      .then((full) => {
        // Only apply if the user hasn't switched to a different community
        if (cancelled || fetchedCommunityRef.current !== cId) return;
        setCommunities((prev) =>
          prev.map((c) => ((c.id ?? c._id) === cId ? { ...c, ...full } : c)),
        );
        setActiveCommunity((prev) => {
          const prevId = prev?.id ?? prev?._id;
          // Guard: only merge if still on the same community
          if (prevId !== cId) return prev;
          return { ...prev, ...full };
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeCommunity?.id, activeCommunity?._id, token]);

  /* Re-fetch community data when online count changes (someone joined/left).
     This updates activeCommunity.members so the sidebar member list stays in sync. */
  const prevOnlineCountRef = useRef(onlineCount);
  useEffect(() => {
    // Skip if the count hasn't actually changed (initial render or same value)
    if (prevOnlineCountRef.current === onlineCount) return;
    prevOnlineCountRef.current = onlineCount;

    const cId = activeCommunity?.id ?? activeCommunity?._id;
    if (!cId || !token) return;

    console.log("[Dashboard] Online count changed to", onlineCount, "→ re-fetching community", cId);
    getCommunity(token, cId)
      .then((full) => {
        setCommunities((prev) =>
          prev.map((c) =>
            (c.id ?? c._id) === cId ? { ...c, ...full } : c,
          ),
        );
        setActiveCommunity((prev) => {
          const prevId = prev?.id ?? prev?._id;
          if (prevId !== cId) return prev;
          return { ...prev, ...full };
        });
      })
      .catch(() => {});
  }, [onlineCount, activeCommunity?.id, activeCommunity?._id, token]);

  const sidebarViews = ["communities", "friends", "archive", "discover"];
  const showSidebar = sidebarViews.includes(activeView);

  const renderContent = () => {
    switch (activeView) {
      case "direct_message":
        return <AllChatsView />;
      case "friends":
        return <FriendsView />;
      case "discover":
        return (
          <DiscoverView
            myCommunities={communities}
            onSelectCommunity={setDiscoverCommunity}
            onJoinCommunity={async (communityId) => {
              await joinCommunity(token, communityId);
              // Notify backend via socket so it broadcasts presence_update to all members
              const s = getSocket();
              if (s?.connected) {
                s.emit("join_room", { communityId });
                console.log("[Discover] Emitted join_room for:", communityId);
              }
              const data = await getMyCommunities(token);
              const list = Array.isArray(data)
                ? data
                : (data.communities ?? []);
              setCommunities(list);
            }}
          />
        );
      case "archive":
        return <ArchiveView />;
      case "communities":
      default:
        return (
          <div className="flex flex-1 min-w-0 bg-card rounded-3xl overflow-hidden">
            <ChatList
              communities={communities}
              activeCommunity={activeCommunity}
              onSelect={(c) => {
                fetchedCommunityRef.current = null;
                setActiveCommunity(c);
              }}
              onCreateCommunity={async (
                name,
                desc,
                restrictedWords,
                avatar,
              ) => {
                const created = await createCommunity(
                  token,
                  name,
                  desc,
                  restrictedWords,
                  avatar,
                );
                const c = created.community ?? created;
                setCommunities((prev) => [c, ...prev]);
                setActiveCommunity(c);
                return c;
              }}
              onJoinCommunity={async (communityId) => {
                await joinCommunity(token, communityId);
                // Notify backend via socket so it broadcasts presence_update to all members
                const s = getSocket();
                if (s?.connected) {
                  s.emit("join_room", { communityId });
                  console.log("[ChatList] Emitted join_room for:", communityId);
                }
                const data = await getMyCommunities(token);
                const list = Array.isArray(data)
                  ? data
                  : (data.communities ?? []);
                setCommunities(list);
                const joined = list.find(
                  (c) => c.id === communityId || c._id === communityId,
                );
                if (joined) setActiveCommunity(joined);
              }}
            />
            <ChatArea
              community={activeCommunity}
              messages={messages}
              onMessagesChange={setMessages}
              onOnlineUserIdsChange={setOnlineUserIds}
              onOnlineCountChange={setOnlineCount}
              onlineCount={onlineCount}
              onEditCommunity={async (communityId, updates) => {
                const updated = await updateCommunity(
                  token,
                  communityId,
                  updates,
                );
                const c = updated.community ?? updated;
                setCommunities((prev) =>
                  prev.map((x) =>
                    (x.id ?? x._id) === communityId ? { ...x, ...c } : x,
                  ),
                );
                setActiveCommunity((prev) => {
                  const prevId = prev?.id ?? prev?._id;
                  if (prevId !== communityId) return prev;
                  return { ...prev, ...c };
                });
              }}
              onDeleteCommunity={async (communityId) => {
                await deleteCommunity(token, communityId);
                setCommunities((prev) =>
                  prev.filter((c) => (c.id ?? c._id) !== communityId),
                );
                setActiveCommunity((cur) =>
                  (cur?.id ?? cur?._id) === communityId ? null : cur,
                );
              }}
              onLeaveCommunity={async (communityId) => {
                // Notify backend via socket BEFORE removing from state
                // so it broadcasts presence_update to remaining members
                const s = getSocket();
                if (s?.connected) {
                  s.emit("leave_room", { communityId });
                  console.log("[Dashboard] Emitted leave_room for:", communityId);
                }
                await leaveCommunity(token, communityId);
                setCommunities((prev) =>
                  prev.filter((c) => (c.id ?? c._id) !== communityId),
                );
                setActiveCommunity((cur) =>
                  (cur?.id ?? cur?._id) === communityId ? null : cur,
                );
              }}
              onDeleteMessage={async (communityId, messageId) => {
                await deleteMessage(token, communityId, messageId);
              }}
            />
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-dark p-3 gap-3">
      <LeftNav
        activeView={activeView}
        onViewChange={setActiveView}
        onLogout={logout}
      />
      {renderContent()}
      {showSidebar &&
        (() => {
          const textMessagesCount = messages.filter(
            (m) => !m.type || m.type !== "audio",
          ).length;
          const audioMessagesCount = messages.filter(
            (m) => m.type === "audio",
          ).length;
          return (
            <RightSidebar
              mode={activeView}
              discoverCommunity={discoverCommunity}
              activeCommunity={activeCommunity}
              textMessagesCount={textMessagesCount}
              audioMessagesCount={audioMessagesCount}
              onlineUserIds={onlineUserIds}
              onlineCount={onlineCount}
              onMakeAdmin={async (communityId, userId) => {
                await addAdmin(token, communityId, userId);
                const full = await getCommunity(token, communityId);
                setCommunities((prev) =>
                  prev.map((c) =>
                    (c.id ?? c._id) === communityId ? { ...c, ...full } : c,
                  ),
                );
                setActiveCommunity((prev) => {
                  const prevId = prev?.id ?? prev?._id;
                  if (prevId !== communityId) return prev;
                  return { ...prev, ...full };
                });
              }}
              onRemoveAdmin={async (communityId, userId) => {
                await removeAdmin(token, communityId, userId);
                const full = await getCommunity(token, communityId);
                setCommunities((prev) =>
                  prev.map((c) =>
                    (c.id ?? c._id) === communityId ? { ...c, ...full } : c,
                  ),
                );
                setActiveCommunity((prev) => {
                  const prevId = prev?.id ?? prev?._id;
                  if (prevId !== communityId) return prev;
                  return { ...prev, ...full };
                });
              }}
            />
          );
        })()}
    </div>
  );
}

function App() {
  const { token } = useAuth();

  return (
    <Routes>
      <Route path="/" element={token ? <Dashboard /> : <LandingPage />} />
      <Route
        path="/auth"
        element={token ? <Navigate to="/" replace /> : <AuthPage />}
      />
      <Route
        path="/*"
        element={token ? <Dashboard /> : <Navigate to="/" replace />}
      />
    </Routes>
  );
}

export default App;
