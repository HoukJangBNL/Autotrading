import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Typography,
  CircularProgress,
  Alert,
  useTheme,
  Stack,
  Divider,
} from '@mui/material';
import {
  Login as LoginIcon,
  TrendingUp as TrendingUpIcon,
  DeveloperMode as DeveloperModeIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useAppSelector } from '../store/hooks';

export const Login: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login, devLogin } = useAuth();
  const { loading, error } = useAppSelector((state) => state.auth);

  const from = location.state?.from?.pathname || '/dashboard';

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  const handleLogin = () => {
    login();
  };

  const handleDevLogin = () => {
    devLogin();
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `linear-gradient(45deg, ${theme.palette.primary.dark} 30%, ${theme.palette.primary.main} 90%)`,
      }}
    >
      <Container maxWidth="sm">
        <Card
          elevation={3}
          sx={{
            p: 4,
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
          }}
        >
          <CardContent>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                mb: 4,
              }}
            >
              <TrendingUpIcon
                sx={{
                  fontSize: 64,
                  color: theme.palette.primary.main,
                  mb: 2,
                }}
              />
              <Typography variant="h4" component="h1" gutterBottom>
                AutoTrading System
              </Typography>
              <Typography variant="body1" color="text.secondary" align="center">
                Professional Algorithmic Trading Platform
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
            )}

            <Stack spacing={3}>
              <Typography variant="body2" color="text.secondary" align="center">
                Connect your Schwab account to start trading
              </Typography>

              <Button
                fullWidth
                variant="contained"
                size="large"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <LoginIcon />}
                onClick={handleLogin}
                disabled={loading}
                sx={{
                  py: 1.5,
                  fontSize: '1.1rem',
                  fontWeight: 500,
                }}
              >
                {loading ? 'Redirecting...' : 'Login with Schwab'}
              </Button>

              {process.env.NODE_ENV === 'development' && (
                <>
                  <Divider sx={{ my: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      OR
                    </Typography>
                  </Divider>

                  <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    startIcon={<DeveloperModeIcon />}
                    onClick={handleDevLogin}
                    sx={{
                      py: 1.5,
                      fontSize: '1rem',
                      fontWeight: 500,
                      borderColor: theme.palette.warning.main,
                      color: theme.palette.warning.main,
                      '&:hover': {
                        borderColor: theme.palette.warning.dark,
                        backgroundColor: theme.palette.warning.dark + '10',
                      },
                    }}
                  >
                    Development Mode
                  </Button>

                  <Alert severity="warning" sx={{ mt: 2 }}>
                    <Typography variant="caption">
                      Development mode bypasses authentication. Use only for frontend development.
                    </Typography>
                  </Alert>
                </>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="caption" color="text.secondary" display="block" align="center">
                  By logging in, you authorize this application to access your Schwab account
                  for trading activities. Your credentials are securely handled through Schwab's
                  OAuth 2.0 authentication.
                </Typography>
              </Box>
            </Stack>
          </CardContent>
        </Card>

        <Typography
          variant="body2"
          color="white"
          align="center"
          sx={{ mt: 3, opacity: 0.8 }}
        >
          © 2024 AutoTrading System. All rights reserved.
        </Typography>
      </Container>
    </Box>
  );
};