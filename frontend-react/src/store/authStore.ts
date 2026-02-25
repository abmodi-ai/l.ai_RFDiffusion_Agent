/**
 * Zustand store for authentication state.
 *
 * Listens for `ligant:auth-expired` events dispatched by the API client
 * when a 401 is received, automatically clearing state so the UI shows
 * the login form.
 */

import { create } from 'zustand';
import type { UserProfile } from '@/types';
import * as api from '@/api/client';

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => {
  // Listen for auth-expired events from the API client
  if (typeof window !== 'undefined') {
    window.addEventListener('ligant:auth-expired', () => {
      set({
        token: null,
        user: null,
        error: 'Session expired — please sign in again.',
      });
    });
  }

  return {
    token: localStorage.getItem('ligant_token'),
    user: null,
    isLoading: false,
    error: null,

    login: async (email, password) => {
      set({ isLoading: true, error: null });
      try {
        const res = await api.login(email, password);
        localStorage.setItem('ligant_token', res.token);
        set({
          token: res.token,
          user: {
            user_id: res.user_id,
            email: res.email,
            display_name: res.display_name,
            is_admin: false,
            created_at: new Date().toISOString(),
          },
          isLoading: false,
        });
      } catch (err) {
        set({ error: (err as Error).message, isLoading: false });
      }
    },

    register: async (email, password, displayName) => {
      set({ isLoading: true, error: null });
      try {
        const res = await api.register(email, password, displayName);
        localStorage.setItem('ligant_token', res.token);
        set({
          token: res.token,
          user: {
            user_id: res.user_id,
            email: res.email,
            display_name: res.display_name,
            is_admin: false,
            created_at: new Date().toISOString(),
          },
          isLoading: false,
        });
      } catch (err) {
        set({ error: (err as Error).message, isLoading: false });
      }
    },

    logout: async () => {
      try {
        await api.logout();
      } catch {
        // Ignore errors during logout
      }
      localStorage.removeItem('ligant_token');
      set({ token: null, user: null });
    },

    checkAuth: async () => {
      const token = localStorage.getItem('ligant_token');
      if (!token) {
        set({ token: null, user: null });
        return;
      }
      set({ isLoading: true });
      try {
        const user = await api.getMe();
        set({ token, user, isLoading: false });
      } catch {
        localStorage.removeItem('ligant_token');
        set({ token: null, user: null, isLoading: false });
      }
    },

    clearError: () => set({ error: null }),
  };
});
