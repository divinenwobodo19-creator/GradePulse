"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import { api, UNAUTHORIZED_EVENT } from "./api";
import type { User } from "./types";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, schoolName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Cache user across provider mounts (survives hot reload in dev)
let cachedUser: User | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(cachedUser);
  const [loading, setLoading] = useState(!cachedUser);
  const initRef = useRef(false);

  useEffect(() => {
    const handleUnauthorized = () => {
      cachedUser = null;
      api.setToken(null);
      setUser(null);
      setLoading(false);
    };

    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    const initialize = async () => {
      const token = api.getToken();
      if (!token || cachedUser) {
        setLoading(false);
        return;
      }

      try {
        const data = await api.me();
        const u: User = {
          id: data.id,
          email: data.email,
          school_id: data.school_id,
          school_name: data.school_name,
        };
        cachedUser = u;
        setUser(u);
      } catch {
        cachedUser = null;
        api.setToken(null);
      } finally {
        setLoading(false);
      }
    };

    void initialize();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.login(email, password);
    const u: User = {
      id: data.id,
      email: data.email,
      school_id: data.school_id,
      school_name: data.school_name,
    };
    cachedUser = u;
    setUser(u);
  }, []);

  const signup = useCallback(
    async (email: string, password: string, schoolName: string) => {
      const data = await api.signup(email, password, schoolName);
      const u: User = {
        id: data.id,
        email: data.email,
        school_id: data.school_id,
        school_name: data.school_name,
      };
      cachedUser = u;
      setUser(u);
    },
    []
  );

  const logout = useCallback(() => {
    cachedUser = null;
    setUser(null);
    api.logout();
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
