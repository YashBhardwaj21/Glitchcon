require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const supabase = require('./config/db');
const initChatSocket = require('./Sockets/chatSocket');

const app = express();

// Middleware
app.use(cors({
  origin: process.env.CLIENT_ORIGIN || '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));
app.use(express.json());

// Routes
app.get('/health', (req, res) => {
  return res.status(200).json({ status: 'ok' });
})
app.use('/api/auth', require('./routes/authRoutes'));
app.use('/api/communities', require('./routes/communityRoutes'));
app.use('/api/upload', require('./routes/uploadRoutes'));

// Health check
app.get('/', (req, res) => res.json({ status: 'API is running' }));

// HTTP server
const server = http.createServer(app);

// Socket.io — mirrors the Express CORS config
const io = new Server(server, {
  cors: {
    origin: process.env.CLIENT_ORIGIN || '*',
    methods: ['GET', 'POST'],
  },
});

initChatSocket(io);

// Make io accessible to route controllers via req.app.get('io')
app.set('io', io);

const PORT = process.env.PORT || 5000;

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = { app, server };

