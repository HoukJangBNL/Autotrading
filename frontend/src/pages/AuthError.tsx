import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Button,
  Alert,
  Paper,
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export const AuthError: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const errorMessage = searchParams.get('error');

  const handleBackToLogin = () => {
    navigate('/login');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'background.default',
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={3}
          sx={{
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <ErrorOutlineIcon
            sx={{
              fontSize: 64,
              color: 'error.main',
            }}
          />
          <Typography variant="h4" component="h1" gutterBottom>
            Authentication Failed
          </Typography>
          <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
            <Typography variant="body2">
              We couldn't complete the authentication process with Schwab. 
              {errorMessage && (
                <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                  <Typography variant="caption" component="pre" sx={{ fontFamily: 'monospace' }}>
                    Error: {decodeURIComponent(errorMessage)}
                  </Typography>
                </Box>
              )}
              <Typography variant="body2" sx={{ mt: 1 }}>
                This might happen if:
              </Typography>
            </Typography>
            <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
              <li>You denied the authorization request</li>
              <li>The authentication session expired</li>
              <li>There was a connection issue</li>
              <li>Callback URL mismatch in Schwab Developer Portal</li>
            </Box>
          </Alert>
          <Typography variant="body1" color="text.secondary" align="center">
            Please try logging in again. If the problem persists, contact support.
          </Typography>
          <Button
            variant="contained"
            size="large"
            startIcon={<ArrowBackIcon />}
            onClick={handleBackToLogin}
            sx={{ mt: 3 }}
          >
            Back to Login
          </Button>
        </Paper>
      </Container>
    </Box>
  );
};