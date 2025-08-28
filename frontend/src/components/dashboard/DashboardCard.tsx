import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Tooltip,
  IconButton,
  Skeleton,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';

interface DashboardCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  change?: number;
  changeLabel?: string;
  tooltip?: string;
  loading?: boolean;
  icon?: React.ReactNode;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info';
  onClick?: () => void;
}

export const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  value,
  subtitle,
  change,
  changeLabel,
  tooltip,
  loading = false,
  icon,
  color = 'primary',
  onClick,
}) => {
  const getChangeColor = () => {
    if (!change) return 'text.secondary';
    return change >= 0 ? 'success.main' : 'error.main';
  };

  const getTrendIcon = () => {
    if (!change) return null;
    return change >= 0 ? <TrendingUpIcon fontSize="small" /> : <TrendingDownIcon fontSize="small" />;
  };

  const formatChange = (val: number) => {
    const formatted = Math.abs(val).toFixed(2);
    return `${val >= 0 ? '+' : '-'}${formatted}%`;
  };

  return (
    <Card
      sx={{
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.3s',
        '&:hover': onClick ? {
          transform: 'translateY(-2px)',
          boxShadow: (theme) => theme.shadows[4],
        } : {},
      }}
      onClick={onClick}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            {icon && (
              <Box color={`${color}.main`}>{icon}</Box>
            )}
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
          </Box>
          {tooltip && (
            <Tooltip title={tooltip} placement="top">
              <IconButton size="small">
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        <Box>
          {loading ? (
            <>
              <Skeleton variant="text" width="60%" height={40} />
              <Skeleton variant="text" width="40%" height={20} />
            </>
          ) : (
            <>
              <Typography variant="h4" component="div" gutterBottom>
                {value}
              </Typography>
              
              {(change !== undefined || subtitle) && (
                <Box display="flex" alignItems="center" gap={0.5}>
                  {change !== undefined && (
                    <>
                      <Box display="flex" alignItems="center" color={getChangeColor()}>
                        {getTrendIcon()}
                        <Typography variant="body2" component="span">
                          {formatChange(change)}
                        </Typography>
                      </Box>
                      {changeLabel && (
                        <Typography variant="body2" color="text.secondary" component="span">
                          {changeLabel}
                        </Typography>
                      )}
                    </>
                  )}
                  {subtitle && change === undefined && (
                    <Typography variant="body2" color="text.secondary">
                      {subtitle}
                    </Typography>
                  )}
                </Box>
              )}
            </>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};