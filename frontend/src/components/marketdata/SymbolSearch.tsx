import React, { useState, useEffect, useRef } from 'react';
import {
  Autocomplete,
  TextField,
  Paper,
  Box,
  Typography,
  Chip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Divider,
} from '@mui/material';
import {
  Search as SearchIcon,
  TrendingUp as TrendingUpIcon,
  History as HistoryIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { useDebounce } from 'react-use';

interface Symbol {
  symbol: string;
  name: string;
  exchange?: string;
  type?: string;
}

interface SymbolSearchProps {
  onSymbolSelect: (symbol: string) => void;
  currentSymbol?: string;
}

const POPULAR_SYMBOLS: Symbol[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
  { symbol: 'MSFT', name: 'Microsoft Corp.', exchange: 'NASDAQ' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ' },
  { symbol: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NASDAQ' },
  { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ' },
  { symbol: 'NVDA', name: 'NVIDIA Corp.', exchange: 'NASDAQ' },
  { symbol: 'META', name: 'Meta Platforms', exchange: 'NASDAQ' },
  { symbol: 'BRK.B', name: 'Berkshire Hathaway', exchange: 'NYSE' },
];

export const SymbolSearch: React.FC<SymbolSearchProps> = ({ onSymbolSelect, currentSymbol }) => {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [options, setOptions] = useState<Symbol[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load recent searches from localStorage
  useEffect(() => {
    const recent = localStorage.getItem('recentSymbolSearches');
    if (recent) {
      setRecentSearches(JSON.parse(recent));
    }
  }, []);

  // Debounce search input
  useDebounce(
    () => {
      if (inputValue.length > 0) {
        searchSymbols(inputValue);
      } else {
        setOptions(POPULAR_SYMBOLS);
      }
    },
    300,
    [inputValue]
  );

  const searchSymbols = async (query: string) => {
    setLoading(true);
    try {
      // In production, this would be an API call
      // For now, filter from popular symbols
      const filtered = POPULAR_SYMBOLS.filter(
        (s) =>
          s.symbol.toUpperCase().includes(query.toUpperCase()) ||
          s.name.toUpperCase().includes(query.toUpperCase())
      );
      setOptions(filtered);
    } catch (error) {
      console.error('Error searching symbols:', error);
      setOptions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSymbolSelect = (symbol: string) => {
    onSymbolSelect(symbol);
    
    // Update recent searches
    const newRecent = [symbol, ...recentSearches.filter((s) => s !== symbol)].slice(0, 5);
    setRecentSearches(newRecent);
    localStorage.setItem('recentSymbolSearches', JSON.stringify(newRecent));
    
    setOpen(false);
    setInputValue('');
  };

  const clearRecentSearches = () => {
    setRecentSearches([]);
    localStorage.removeItem('recentSymbolSearches');
  };

  return (
    <Box sx={{ position: 'relative', width: '100%', maxWidth: 400 }}>
      <Autocomplete
        open={open}
        onOpen={() => setOpen(true)}
        onClose={() => setOpen(false)}
        inputValue={inputValue}
        onInputChange={(event, newInputValue) => {
          setInputValue(newInputValue);
        }}
        options={options}
        getOptionLabel={(option) => (typeof option === 'string' ? option : option.symbol)}
        renderOption={(props, option) => (
          <Box component="li" {...props}>
            <Box sx={{ width: '100%' }}>
              <Typography variant="body1" fontWeight="bold">
                {option.symbol}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {option.name} • {option.exchange}
              </Typography>
            </Box>
          </Box>
        )}
        loading={loading}
        freeSolo
        renderInput={(params) => (
          <TextField
            {...params}
            placeholder="Search symbols..."
            variant="outlined"
            size="small"
            inputRef={searchInputRef}
            InputProps={{
              ...params.InputProps,
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
          />
        )}
        PaperComponent={(props) => (
          <Paper {...props} elevation={3}>
            {props.children}
            
            {recentSearches.length > 0 && inputValue.length === 0 && (
              <>
                <Divider />
                <Box sx={{ p: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <HistoryIcon sx={{ mr: 1, fontSize: 20 }} />
                      <Typography variant="caption" fontWeight="bold">
                        Recent Searches
                      </Typography>
                    </Box>
                    <IconButton size="small" onClick={clearRecentSearches}>
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </Box>
                  <List dense>
                    {recentSearches.map((symbol) => (
                      <ListItemButton key={symbol} onClick={() => handleSymbolSelect(symbol)}>
                        <ListItemText primary={symbol} />
                      </ListItemButton>
                    ))}
                  </List>
                </Box>
              </>
            )}
            
            {inputValue.length === 0 && (
              <>
                <Divider />
                <Box sx={{ p: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', px: 1, pb: 1 }}>
                    <TrendingUpIcon sx={{ mr: 1, fontSize: 20 }} />
                    <Typography variant="caption" fontWeight="bold">
                      Popular Symbols
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, px: 1 }}>
                    {POPULAR_SYMBOLS.slice(0, 8).map((symbol) => (
                      <Chip
                        key={symbol.symbol}
                        label={symbol.symbol}
                        size="small"
                        onClick={() => handleSymbolSelect(symbol.symbol)}
                        sx={{ cursor: 'pointer' }}
                      />
                    ))}
                  </Box>
                </Box>
              </>
            )}
          </Paper>
        )}
      />
      
      {currentSymbol && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            Current: 
          </Typography>
          <Chip
            label={currentSymbol}
            size="small"
            sx={{ ml: 1 }}
            color="primary"
          />
        </Box>
      )}
    </Box>
  );
};