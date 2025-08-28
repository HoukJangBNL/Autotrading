import React, { useState } from 'react';
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Container,
  Paper,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  AccountBalance,
  TrendingUp,
  Notifications,
  Palette,
  Storage,
  Info,
} from '@mui/icons-material';
import { AccountSettings } from '../components/settings/AccountSettings';
import { TradingPreferences } from '../components/settings/TradingPreferences';
import { NotificationSettings } from '../components/settings/NotificationSettings';
import { ApplicationSettings } from '../components/settings/ApplicationSettings';
import { DataManagement } from '../components/settings/DataManagement';
import { SystemInfo } from '../components/settings/SystemInfo';

interface SettingsSection {
  id: string;
  title: string;
  icon: React.ReactElement;
  component: React.ReactElement;
}

export const Settings: React.FC = () => {
  const [expanded, setExpanded] = useState<string | false>('account');

  const handleChange = (panel: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
    setExpanded(isExpanded ? panel : false);
  };

  const sections: SettingsSection[] = [
    {
      id: 'account',
      title: 'Account Settings',
      icon: <AccountBalance />,
      component: <AccountSettings />,
    },
    {
      id: 'trading',
      title: 'Trading Preferences',
      icon: <TrendingUp />,
      component: <TradingPreferences />,
    },
    {
      id: 'notifications',
      title: 'Notification Settings',
      icon: <Notifications />,
      component: <NotificationSettings />,
    },
    {
      id: 'application',
      title: 'Application Settings',
      icon: <Palette />,
      component: <ApplicationSettings />,
    },
    {
      id: 'data',
      title: 'Data Management',
      icon: <Storage />,
      component: <DataManagement />,
    },
    {
      id: 'system',
      title: 'System Information',
      icon: <Info />,
      component: <SystemInfo />,
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure your trading application preferences and system settings
        </Typography>
      </Box>

      <Paper elevation={2}>
        {sections.map((section) => (
          <Accordion
            key={section.id}
            expanded={expanded === section.id}
            onChange={handleChange(section.id)}
            sx={{
              '&:before': {
                display: 'none',
              },
              '&.Mui-expanded': {
                margin: 0,
              },
            }}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              sx={{
                backgroundColor: expanded === section.id ? 'action.selected' : 'background.paper',
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ color: 'primary.main' }}>
                  {section.icon}
                </Box>
                <Typography variant="h6">
                  {section.title}
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 3 }}>
              {section.component}
            </AccordionDetails>
          </Accordion>
        ))}
      </Paper>

      {/* Footer Information */}
      <Box sx={{ mt: 4, mb: 2, textAlign: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          All settings are saved locally in your browser. 
          Your data is never sent to external servers.
        </Typography>
      </Box>
    </Container>
  );
};