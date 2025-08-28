import React, { useState, useMemo } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  InputAdornment,
  IconButton,
  Fab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
  Sort as SortIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { StrategyCard } from './StrategyCard';
import { Strategy, StrategyStatus, StrategyType } from '../../types/strategy';
import { useNavigate } from 'react-router-dom';

interface StrategyListProps {
  strategies: Strategy[];
  onToggle: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
  onClone: (id: string) => void;
  onBacktest: (id: string) => void;
}

export const StrategyList: React.FC<StrategyListProps> = ({
  strategies,
  onToggle,
  onDelete,
  onClone,
  onBacktest,
}) => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StrategyStatus | 'ALL'>('ALL');
  const [typeFilter, setTypeFilter] = useState<StrategyType | 'ALL'>('ALL');
  const [sortBy, setSortBy] = useState<'name' | 'performance' | 'updated'>('updated');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  // Filter and sort strategies
  const filteredStrategies = useMemo(() => {
    let filtered = [...strategies];

    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(
        (s) =>
          s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.symbols.some((sym) => sym.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    }

    // Apply status filter
    if (statusFilter !== 'ALL') {
      filtered = filtered.filter((s) => s.status === statusFilter);
    }

    // Apply type filter
    if (typeFilter !== 'ALL') {
      filtered = filtered.filter((s) => s.type === typeFilter);
    }

    // Sort strategies
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'performance':
          comparison = (a.performance?.totalReturn || 0) - (b.performance?.totalReturn || 0);
          break;
        case 'updated':
          comparison = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [strategies, searchQuery, statusFilter, typeFilter, sortBy, sortOrder]);

  const handleEdit = (id: string) => {
    navigate(`/strategies/edit/${id}`);
  };

  const handleCreate = () => {
    navigate('/strategies/create');
  };

  const handleDeleteClick = (id: string) => {
    setSelectedStrategy(id);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (selectedStrategy) {
      onDelete(selectedStrategy);
    }
    setDeleteDialogOpen(false);
    setSelectedStrategy(null);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('ALL');
    setTypeFilter('ALL');
  };

  const getStrategyStats = () => {
    const active = strategies.filter((s) => s.status === StrategyStatus.ACTIVE).length;
    const testing = strategies.filter((s) => s.status === StrategyStatus.TESTING).length;
    const totalReturn = strategies
      .filter((s) => s.performance)
      .reduce((sum, s) => sum + (s.performance?.totalReturn || 0), 0) / 
      strategies.filter((s) => s.performance).length || 0;

    return { active, testing, totalReturn };
  };

  const stats = getStrategyStats();

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">
          Strategy Management
        </Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleCreate}
        >
          Create Strategy
        </Button>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary" gutterBottom>
              Total Strategies
            </Typography>
            <Typography variant="h4">
              {strategies.length}
            </Typography>
            <Typography variant="caption" color="success.main">
              {stats.active} active
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary" gutterBottom>
              Testing
            </Typography>
            <Typography variant="h4">
              {stats.testing}
            </Typography>
            <Typography variant="caption" color="warning.main">
              In progress
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary" gutterBottom>
              Avg. Return
            </Typography>
            <Typography 
              variant="h4"
              color={stats.totalReturn >= 0 ? 'success.main' : 'error.main'}
            >
              {stats.totalReturn >= 0 ? '+' : ''}{stats.totalReturn.toFixed(2)}%
            </Typography>
            <Typography variant="caption">
              All strategies
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search strategies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StrategyStatus | 'ALL')}
                label="Status"
              >
                <MenuItem value="ALL">All Status</MenuItem>
                <MenuItem value={StrategyStatus.ACTIVE}>Active</MenuItem>
                <MenuItem value={StrategyStatus.INACTIVE}>Inactive</MenuItem>
                <MenuItem value={StrategyStatus.TESTING}>Testing</MenuItem>
                <MenuItem value={StrategyStatus.ERROR}>Error</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as StrategyType | 'ALL')}
                label="Type"
              >
                <MenuItem value="ALL">All Types</MenuItem>
                <MenuItem value={StrategyType.MOMENTUM}>Momentum</MenuItem>
                <MenuItem value={StrategyType.MEAN_REVERSION}>Mean Reversion</MenuItem>
                <MenuItem value={StrategyType.BREAKOUT}>Breakout</MenuItem>
                <MenuItem value={StrategyType.ARBITRAGE}>Arbitrage</MenuItem>
                <MenuItem value={StrategyType.MARKET_MAKING}>Market Making</MenuItem>
                <MenuItem value={StrategyType.CUSTOM}>Custom</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'name' | 'performance' | 'updated')}
                label="Sort By"
              >
                <MenuItem value="name">Name</MenuItem>
                <MenuItem value="performance">Performance</MenuItem>
                <MenuItem value="updated">Last Updated</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={1}>
            <IconButton
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              size="small"
            >
              <SortIcon 
                style={{ 
                  transform: sortOrder === 'desc' ? 'rotate(180deg)' : 'none',
                  transition: 'transform 0.3s',
                }}
              />
            </IconButton>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              onClick={handleClearFilters}
              startIcon={<ClearIcon />}
            >
              Clear
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Strategy Grid */}
      {filteredStrategies.length > 0 ? (
        <Grid container spacing={3}>
          {filteredStrategies.map((strategy) => (
            <Grid item xs={12} sm={6} md={4} key={strategy.id}>
              <StrategyCard
                strategy={strategy}
                onToggle={onToggle}
                onEdit={handleEdit}
                onDelete={handleDeleteClick}
                onClone={onClone}
                onBacktest={onBacktest}
              />
            </Grid>
          ))}
        </Grid>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No strategies found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {searchQuery || statusFilter !== 'ALL' || typeFilter !== 'ALL'
              ? 'Try adjusting your filters'
              : 'Create your first strategy to get started'}
          </Typography>
          {!searchQuery && statusFilter === 'ALL' && typeFilter === 'ALL' && (
            <Button variant="contained" color="primary" onClick={handleCreate}>
              Create Strategy
            </Button>
          )}
        </Paper>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Strategy</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this strategy? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};