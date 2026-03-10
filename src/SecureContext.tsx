import React, { createContext, useContext, useState, ReactNode } from 'react';

// Security Hardening: Remove password from router params, use secure state context instead
interface SecureContextType {
    sessionPassword?: string;
    setSessionPassword: (pw: string) => void;
    clearSession: () => void;
}

const SecureContext = createContext<SecureContextType>({
    setSessionPassword: () => {},
    clearSession: () => {}
});

export const SecureProvider: React.FC<{children: ReactNode}> = ({ children }) => {
    const [sessionPassword, setSessionPassword] = useState<string>();

    const clearSession = () => {
        setSessionPassword(undefined);
    };

    return (
        <SecureContext.Provider value={{ sessionPassword, setSessionPassword, clearSession }}>
            {children}
        </SecureContext.Provider>
    );
};

export const useSecureContext = () => useContext(SecureContext);
