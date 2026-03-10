import { createContext, useContext, useState, useEffect } from "react";
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
} from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    if (!saved) return null;
    const parsed = JSON.parse(saved);
    // If the stored user is missing an id, the session is stale — force re-login
    if (!parsed?.id) {
      localStorage.removeItem("user");
      localStorage.removeItem("token");
      return null;
    }
    return parsed;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Sync: if user was cleared due to stale data, also clear token state
  useEffect(() => {
    if (!user && token) {
      const saved = localStorage.getItem("user");
      if (!saved) setToken(null);
    }
  }, []);

  useEffect(() => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  }, [token]);

  useEffect(() => {
    if (user) localStorage.setItem("user", JSON.stringify(user));
    else localStorage.removeItem("user");
  }, [user]);

  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiLogin(email, password);
      setToken(data.token);
      const { token: _t, ...userData } = data;
      setUser(userData); // { id, email, name }
      return data;
    } catch (err) {
      setError(err.message || "Login failed");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (name, email, password, avatar) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRegister(name, email, password, avatar);
      setToken(data.token);
      const { token: _t, ...userData } = data;
      setUser(userData); // { id, email, name, avatar_url }
      return data;
    } catch (err) {
      setError(err.message || "Registration failed");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      if (token) await apiLogout(token);
    } catch {
      /* clear local state regardless */
    }
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ token, user, loading, error, login, register, logout, setError }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
