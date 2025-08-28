import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Alert,
  Paper,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { useAppDispatch } from '../store/hooks';
import { checkAuthStatus } from '../features/auth/authSlice';

export const AuthSuccess: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  useEffect(() => {
    // Check auth status to update the state
    dispatch(checkAuthStatus()).then(() => {
      // Redirect to dashboard after a short delay
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    });
  }, [dispatch, navigate]);

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
          <CheckCircleOutlineIcon
            sx={{
              fontSize: 64,
              color: 'success.main',
            }}
          />
          <Typography variant="h4" component="h1" gutterBottom>
            Authentication Successful!
          </Typography>
          <Typography variant="body1" color="text.secondary" align="center">
            You have successfully connected your Schwab account.
          </Typography>
          <Box sx={{ mt: 3 }}>
            <CircularProgress size={24} />
          </Box>
          <Typography variant="body2" color="text.secondary">
            Redirecting to dashboard...
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};