import React, { createContext, useContext, useEffect, useState } from "react";
import { http } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem("ota_user");
    return u ? JSON.parse(u) : null;
  });
  const [loading, setLoading] = useState(false);

  const login = async (email, password) => {
    const { data } = await http.post("/auth/login", { email, password });
    localStorage.setItem("ota_token", data.token);
    localStorage.setItem("ota_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("ota_token");
    localStorage.removeItem("ota_user");
    setUser(null);
  };

  useEffect(() => {
    const token = localStorage.getItem("ota_token");
    if (token && !user) {
      setLoading(true);
      http.get("/auth/me")
        .then((r) => { setUser(r.data); localStorage.setItem("ota_user", JSON.stringify(r.data)); })
        .catch(() => logout())
        .finally(() => setLoading(false));
    }
  }, []); // eslint-disable-line

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
