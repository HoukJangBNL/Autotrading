import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
} from '@mui/material';
import { PlayArrow as PlayArrowIcon } from '@mui/icons-material';

export const Backtest: React.FC = () => {
  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          Backtest
        </Typography>
        <Button
          variant="contained"
          startIcon={<PlayArrowIcon />}
          onClick={() => console.log('Run backtest')}
        >
          Run Backtest
        </Button>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Backtest Configuration
            </Typography>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              height={300}
              color="text.secondary"
            >
              Configuration form will be implemented here
            </Box>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Backtests
            </Typography>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              height={300}
              color="text.secondary"
            >
              Backtest history will be implemented here
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Backtest Results
            </Typography>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              height={400}
              color="text.secondary"
            >
              Results visualization will be implemented here
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};