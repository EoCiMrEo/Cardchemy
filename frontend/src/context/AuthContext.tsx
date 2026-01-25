import React, { createContext, useContext, useEffect, useState } from 'react';
import api, { getToken, removeToken, removeRefreshToken, setToken, setRefreshToken } from '../services/api';
import { jwtDecode } from 'jwt-decode';

interface User {
  id: string;
  email: string;
  role: 'instructor' | 'student';
  full_name?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const login = (accessToken: string, refreshToken: string) => {
    setToken(accessToken);
    setRefreshToken(refreshToken);
    
    // Decode token to get user info immediately
    try {
      const decoded: any = jwtDecode(accessToken);
      setUser({
        id: decoded.user_id,
        email: decoded.sub,
        role: decoded.role,
      });
      // Optionally fetch full profile in background
    } catch (e) {
      console.error("Failed to decode token", e);
    }
  };

  const logout = () => {
    removeToken();
    removeRefreshToken();
    setUser(null);
  };

  const checkAuth = async () => {
    setIsLoading(true);
    const token = getToken();
    
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      // Decode token first for instant feedback (optimistic)
      try {
        const decoded: any = jwtDecode(token);
        // Check if expired
        if (decoded.exp * 1000 < Date.now()) {
          throw new Error("Token expired");
        }
        setUser({
          id: decoded.user_id,
          email: decoded.sub,
          role: decoded.role,
        });
      } catch (e) {
        // If decode fails, let the API call verify
        console.log("Local decode failed, verifying with API");
      }

      // Verify with backend
      const response = await api.get('/auth/me');
      setUser(response.data);
    } catch (error) {
      console.error("Auth check failed:", error);
      // Only logout if it's strictly an auth error, not network error
      // But for MVP simplicity, invalid token -> logout
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
