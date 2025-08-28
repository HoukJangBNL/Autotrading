import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { checkAuthStatus, fetchAuthUrl, setAuthenticated, setLoading } from '../features/auth/authSlice';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
  checkAuth: () => void;
  // Development only
  devLogin: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const dispatch = useAppDispatch();
  const { isAuthenticated, authUrl, loading } = useAppSelector((state) => state.auth);
  const [initialCheckDone, setInitialCheckDone] = React.useState(false);

  useEffect(() => {
    // Check auth status on mount
    if (!initialCheckDone) {
      checkAuth();
      setInitialCheckDone(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // checkAuth is intentionally not in deps to prevent loops

  const checkAuth = React.useCallback(async () => {
    // For development, check if dev mode is enabled
    if (process.env.NODE_ENV === 'development' && localStorage.getItem('dev_auth') === 'true') {
      dispatch(setAuthenticated(true));
      return;
    }
    
    try {
      dispatch(setLoading(true));
      await dispatch(checkAuthStatus()).unwrap();
    } catch (error) {
      console.error('Auth check failed:', error);
      // Set authenticated to false on error
      dispatch(setAuthenticated(false));
    }
  }, [dispatch]);

  const login = async () => {
    try {
      // Get auth URL and redirect
      const result = await dispatch(fetchAuthUrl()).unwrap();
      if (result.auth_url) {
        window.location.href = result.auth_url;
      }
    } catch (error) {
      console.error('Login failed:', error);
      // For development, show dev login option
      if (process.env.NODE_ENV === 'development') {
        const useDevAuth = window.confirm('Backend server not available. Use development mode?');
        if (useDevAuth) {
          devLogin();
        }
      }
    }
  };

  const logout = () => {
    // Clear local storage and redirect
    localStorage.removeItem('auth_token');
    localStorage.removeItem('dev_auth');
    dispatch(setAuthenticated(false));
    window.location.href = '/login';
  };

  // Development only - bypass authentication
  const devLogin = () => {
    if (process.env.NODE_ENV === 'development') {
      localStorage.setItem('dev_auth', 'true');
      dispatch(setAuthenticated(true));
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading: loading || !initialCheckDone,
        login,
        logout,
        checkAuth,
        devLogin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};