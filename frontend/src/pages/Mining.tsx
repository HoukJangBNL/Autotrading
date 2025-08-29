import React from 'react';
import { Container, Grid, Typography } from '@mui/material';
import MiningDashboard from '../components/mining/MiningDashboard';
import { MiningModeControl } from '../components/mining/MiningModeControl';
import { MiningMonitor } from '../components/mining/MiningMonitor';

const Mining: React.FC = () => {
  return (
    <Container maxWidth="xl">
      <Typography variant="h4" fontWeight="bold" gutterBottom>
        Data Mining
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} lg={4}>
          <MiningModeControl />
        </Grid>
        <Grid item xs={12} lg={8}>
          <MiningMonitor />
        </Grid>
        <Grid item xs={12}>
          <MiningDashboard />
        </Grid>
      </Grid>
    </Container>
  );
};

export default Mining;