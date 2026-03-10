import { create } from 'zustand';

interface AuthState {
    isUnlocked: boolean;
    sessionToken: string | null;
    setUnlocked: (token: string) => void;
    lock: () => void;
}

/**
 * HIGH: Remove password from router params.
 * Use secure memory state (Zustand) to manage auth status 
 * rather than passing passwords via React Navigation route parameters.
 */
export const useAuthStore = create<AuthState>((set) => ({
    isUnlocked: false,
    sessionToken: null,
    setUnlocked: (token) => set({ isUnlocked: true, sessionToken: token }),
    lock: () => set({ isUnlocked: false, sessionToken: null })
}));
