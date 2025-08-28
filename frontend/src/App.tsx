import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Provider } from 'react-redux';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { store } from './store/store';
import { AuthProvider } from './contexts/AuthContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { MainLayout } from './layouts/MainLayout';
import { PrivateRoute } from './components/common/PrivateRoute';
import {
  Dashboard,
  MarketData,
  Strategies,
  Backtest,
  Trading,
  Portfolio,
  Settings,
  Login,
} from './pages';
import { AuthSuccess } from './pages/AuthSuccess';
import { AuthError } from './pages/AuthError';

function App() {
  return (
    <Provider store={store}>
      <SettingsProvider>
        <AuthProvider>
          <Router>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/auth/success" element={<AuthSuccess />} />
              <Route path="/auth/error" element={<AuthError />} />
              <Route
                path="/"
                element={
                  <PrivateRoute>
                    <MainLayout />
                  </PrivateRoute>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="market" element={<MarketData />} />
                <Route path="strategies" element={<Strategies />} />
                <Route path="backtest" element={<Backtest />} />
                <Route path="trading" element={<Trading />} />
                <Route path="portfolio" element={<Portfolio />} />
                <Route path="settings" element={<Settings />} />
              </Route>
            </Routes>
          </Router>
          <ToastContainer 
            position="bottom-right"
            theme="dark"
            newestOnTop={true}
          />
        </AuthProvider>
      </SettingsProvider>
    </Provider>
  );
}

export default App;
