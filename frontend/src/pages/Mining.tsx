import React from 'react';
import { Container, Grid, Typography, Box } from '@mui/material';
import { MiningModeControl } from '../components/mining/MiningModeControl';
import { SimpleMiningMonitor } from '../components/mining/SimpleMiningMonitor';

const Mining: React.FC = () => {
  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Data Mining
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage historical data collection for portfolio optimization and market analysis
        </Typography>
      </Box>
      
      <Grid container spacing={3}>
        <Grid item xs={12} lg={5}>
          <MiningModeControl />
        </Grid>
        <Grid item xs={12} lg={7}>
          <SimpleMiningMonitor />
        </Grid>
      </Grid>
    </Container>
  );
};

export default Mining;