/**
 * Remove password from router params
 * Use an in-memory secure state manager / context provider instead.
 */
export class SecureSessionManager {
    private static sessionPassword: string | null = null;

    static setSessionPassword(password: string) {
        this.sessionPassword = password;
    }

    static getSessionPassword(): string {
        if (!this.sessionPassword) {
            throw new Error('No active secure session');
        }
        return this.sessionPassword;
    }

    static clearSession() {
        this.sessionPassword = null;
    }
}
