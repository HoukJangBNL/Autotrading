// Authentication state management slice

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { authApi } from '../../services/api';

interface AuthState {
  isAuthenticated: boolean;
  authUrl: string | null;
  expiresAt: string | null;
  refreshExpiresAt: string | null;
  scope: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  isAuthenticated: false,
  authUrl: null,
  expiresAt: null,
  refreshExpiresAt: null,
  scope: null,
  loading: false, // Set to false initially
  error: null,
};

// Async thunks
export const fetchAuthUrl = createAsyncThunk(
  'auth/fetchAuthUrl',
  async () => {
    const response = await authApi.getLoginUrl();
    return response.data;
  }
);

export const checkAuthStatus = createAsyncThunk(
  'auth/checkStatus',
  async () => {
    const response = await authApi.getStatus();
    return response.data;
  }
);

export const refreshToken = createAsyncThunk(
  'auth/refreshToken',
  async () => {
    const response = await authApi.refreshToken();
    return response.data;
  }
);

export const logout = createAsyncThunk(
  'auth/logout',
  async () => {
    const response = await authApi.logout();
    return response.data;
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setAuthenticated: (state, action) => {
      state.isAuthenticated = action.payload;
      state.loading = false;
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch auth URL
      .addCase(fetchAuthUrl.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchAuthUrl.fulfilled, (state, action) => {
        state.loading = false;
        state.authUrl = action.payload.auth_url;
      })
      .addCase(fetchAuthUrl.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch auth URL';
      })
      // Check auth status
      .addCase(checkAuthStatus.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(checkAuthStatus.fulfilled, (state, action) => {
        state.loading = false;
        state.isAuthenticated = action.payload.is_authenticated;
        state.expiresAt = action.payload.expires_at;
        state.refreshExpiresAt = action.payload.refresh_expires_at;
        state.scope = action.payload.scope;
      })
      .addCase(checkAuthStatus.rejected, (state, action) => {
        state.loading = false;
        state.isAuthenticated = false;
        state.error = action.error.message || 'Failed to check auth status';
      })
      // Refresh token
      .addCase(refreshToken.fulfilled, (state, action) => {
        state.isAuthenticated = true;
        state.expiresAt = action.payload.expires_at;
      })
      // Logout
      .addCase(logout.fulfilled, (state) => {
        state.isAuthenticated = false;
        state.expiresAt = null;
        state.refreshExpiresAt = null;
        state.scope = null;
      });
  },
});

export const { setAuthenticated, setLoading } = authSlice.actions;
export default authSlice.reducer;