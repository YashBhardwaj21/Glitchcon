import { useState, useEffect } from "react";
import { connectSocket } from "../socket";

/**
 * useCommunityPresence
 *
 * Custom hook for managing real-time online presence in a community.
 *
 * @param {string} communityId - The ID of the community
 * @param {string} token - JWT authentication token
 * @returns {Object} { onlineCount, onlineUserIds }
 *   - onlineCount: number of users currently online
 *   - onlineUserIds: Set of user IDs that are online (for O(1) lookup)
 *
 * Workflow:
 * 1. On mount, fetches community data from REST API to seed initial state
 * 2. Connects to Socket.IO with JWT auth
 * 3. Emits 'join_room' to register in the community's presence room
 * 4. Listens for 'presence_update' events for real-time sync
 * 5. On unmount, cleans up socket listeners
 */
export const useCommunityPresence = (communityId, token) => {
  const [onlineCount, setOnlineCount] = useState(0);
  const [onlineUserIds, setOnlineUserIds] = useState(new Set());

  // ──────────────────────────────────────────────────────────────
  // STEP 1: Fetch initial community data from REST API
  // ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!communityId || !token) return;

    const fetchCommunityData = async () => {
      try {
        const response = await fetch(`/api/communities/${communityId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error(
            `Failed to fetch community: ${response.status} ${response.statusText}`,
          );
        }

        const data = await response.json();

        // Seed initial online count
        if (data.online_members != null) {
          setOnlineCount(data.online_members);
        }

        // Seed initial online user IDs
        if (data.online_member_list && Array.isArray(data.online_member_list)) {
          const userIds = new Set(
            data.online_member_list.map((m) => m.userId || m.id),
          );
          setOnlineUserIds(userIds);
          console.log(
            "[useCommunityPresence] Initial state seeded:",
            data.online_members,
            "online",
          );
        }
      } catch (error) {
        console.error(
          "[useCommunityPresence] Failed to fetch community:",
          error,
        );
      }
    };

    fetchCommunityData();
  }, [communityId, token]);

  // ──────────────────────────────────────────────────────────────
  // STEP 2 & 3: Socket connection, join_room, and presence_update
  // ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!communityId || !token) return;

    // Connect to socket with JWT authentication
    const socket = connectSocket(token);

    // Helper function to emit join_room
    const emitJoinRoom = () => {
      socket.emit("join_room", { communityId });
      console.log(
        "[useCommunityPresence] Emitted join_room for communityId:",
        communityId,
      );
    };

    // Emit immediately if already connected, or wait for connection
    if (socket.connected) {
      emitJoinRoom();
    } else {
      socket.once("connect", emitJoinRoom);
    }

    // Handler for real-time presence updates
    const handlePresenceUpdate = ({ online_members, members }) => {
      console.log("[useCommunityPresence] Received presence_update:", {
        online_members,
        memberCount: members?.length || 0,
      });

      // Update online count
      setOnlineCount(online_members ?? 0);

      // Update online user IDs (deduplicated set)
      if (Array.isArray(members)) {
        const userIds = new Set(members.map((m) => m.userId || m.id));
        setOnlineUserIds(userIds);
      }
    };

    // Register the presence_update listener
    socket.on("presence_update", handlePresenceUpdate);

    // ──────────────────────────────────────────────────────────────
    // Cleanup: Remove listeners when component unmounts
    // ──────────────────────────────────────────────────────────────
    return () => {
      socket.off("presence_update", handlePresenceUpdate);
      console.log(
        "[useCommunityPresence] Cleaned up presence_update listener for:",
        communityId,
      );
      // Note: We don't call socket.disconnect() here because the socket
      // is a singleton shared across the app. Full disconnect should be
      // managed at the app level in useAuth/logout.
    };
  }, [communityId, token]);

  return {
    onlineCount,
    onlineUserIds,
  };
};
