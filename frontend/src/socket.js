import { io } from "socket.io-client";

let socket = null;

/** Returns a singleton socket connection authenticated with the JWT token */
export const connectSocket = (token) => {
  // Reuse existing connected socket
  if (socket?.connected) return socket;

  // Disconnect stale socket if any
  if (socket) {
    socket.disconnect();
    socket = null;
  }

  socket = io(import.meta.env.VITE_BACKEND_URL, {
    auth: { token },
    transports: ["websocket", "polling"], // try websocket first
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
  });

  socket.on("connect", () => {
    console.log("[Socket] Connected:", socket.id);
  });

  socket.on("connect_error", (err) => {
    console.error("[Socket] Connection error:", err.message);
  });

  socket.on("disconnect", (reason) => {
    console.log("[Socket] Disconnected:", reason);
  });

  return socket;
};

export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
};

export const getSocket = () => socket;
