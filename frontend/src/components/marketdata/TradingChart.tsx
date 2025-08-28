import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  HistogramData,
  ColorType,
  CrosshairMode,
} from 'lightweight-charts';
import {
  Box,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  Divider,
} from '@mui/material';
import {
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  ShowChart as LineIcon,
  BarChart as CandleIcon,
  Timeline as TimelineIcon,
  Brush as DrawIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';

interface TradingChartProps {
  symbol: string;
  data?: CandlestickData[];
  onTimeframeChange?: (timeframe: string) => void;
}

const TIMEFRAMES = [
  { label: '1m', value: '1' },
  { label: '5m', value: '5' },
  { label: '15m', value: '15' },
  { label: '30m', value: '30' },
  { label: '1h', value: '60' },
  { label: '1d', value: 'D' },
];

export const TradingChart: React.FC<TradingChartProps> = ({ symbol, data, onTimeframeChange }) => {
  const theme = useTheme();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candlestickSeries = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeries = useRef<ISeriesApi<'Histogram'> | null>(null);
  const maSeries = useRef<ISeriesApi<'Line'> | null>(null);
  const ma20Series = useRef<ISeriesApi<'Line'> | null>(null);
  const bbUpperSeries = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerSeries = useRef<ISeriesApi<'Line'> | null>(null);
  
  const [timeframe, setTimeframe] = useState('5');
  const [chartType, setChartType] = useState<'candle' | 'line'>('candle');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showMA, setShowMA] = useState(true);
  const [showBB, setShowBB] = useState(false);
  const [showVolume, setShowVolume] = useState(true);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    chart.current = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { type: ColorType.Solid, color: theme.palette.background.paper },
        textColor: theme.palette.text.primary,
      },
      grid: {
        vertLines: { color: theme.palette.divider },
        horzLines: { color: theme.palette.divider },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: theme.palette.divider,
      },
      timeScale: {
        borderColor: theme.palette.divider,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Create series
    candlestickSeries.current = chart.current.addCandlestickSeries({
      upColor: theme.palette.success.main,
      downColor: theme.palette.error.main,
      borderUpColor: theme.palette.success.main,
      borderDownColor: theme.palette.error.main,
      wickUpColor: theme.palette.success.main,
      wickDownColor: theme.palette.error.main,
    });

    // Create volume series
    volumeSeries.current = chart.current.addHistogramSeries({
      color: theme.palette.primary.main,
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    // Create MA series
    maSeries.current = chart.current.addLineSeries({
      color: theme.palette.warning.main,
      lineWidth: 2,
      title: 'MA 10',
      lastValueVisible: false,
      priceLineVisible: false,
    });

    ma20Series.current = chart.current.addLineSeries({
      color: theme.palette.info.main,
      lineWidth: 2,
      title: 'MA 20',
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // Create Bollinger Bands series
    bbUpperSeries.current = chart.current.addLineSeries({
      color: theme.palette.secondary.main,
      lineWidth: 1,
      title: 'BB Upper',
      lastValueVisible: false,
      priceLineVisible: false,
    });

    bbLowerSeries.current = chart.current.addLineSeries({
      color: theme.palette.secondary.main,
      lineWidth: 1,
      title: 'BB Lower',
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // Handle resize
    const handleResize = () => {
      if (chart.current && chartContainerRef.current) {
        chart.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart.current) {
        chart.current.remove();
      }
    };
  }, [theme]);

  // Update data
  useEffect(() => {
    if (!chart.current || !candlestickSeries.current || !volumeSeries.current) return;

    // Generate mock data if no data provided
    const chartData = data || generateMockData();
    
    // Set candlestick data
    candlestickSeries.current.setData(chartData);
    
    // Set volume data
    const volumeData: HistogramData[] = chartData.map((d) => ({
      time: d.time,
      value: d.volume || Math.random() * 1000000,
      color: d.open <= d.close ? theme.palette.success.main : theme.palette.error.main,
    }));
    volumeSeries.current.setData(volumeData);
    
    // Calculate and set moving averages
    if (showMA) {
      const ma10Data = calculateMA(chartData, 10);
      const ma20Data = calculateMA(chartData, 20);
      maSeries.current?.setData(ma10Data);
      ma20Series.current?.setData(ma20Data);
    }
    
    // Calculate and set Bollinger Bands
    if (showBB) {
      const { upper, lower } = calculateBollingerBands(chartData, 20, 2);
      bbUpperSeries.current?.setData(upper);
      bbLowerSeries.current?.setData(lower);
    }
    
    // Fit content
    chart.current.timeScale().fitContent();
  }, [data, showMA, showBB, theme]);

  const handleTimeframeChange = (_event: React.MouseEvent<HTMLElement>, newTimeframe: string) => {
    if (newTimeframe !== null) {
      setTimeframe(newTimeframe);
      onTimeframeChange?.(newTimeframe);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      chartContainerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const handleSettingsClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleSettingsClose = () => {
    setAnchorEl(null);
  };

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">{symbol}</Typography>
          <ToggleButtonGroup
            value={timeframe}
            exclusive
            onChange={handleTimeframeChange}
            size="small"
          >
            {TIMEFRAMES.map((tf) => (
              <ToggleButton key={tf.value} value={tf.value}>
                {tf.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Chart Type">
            <IconButton
              onClick={() => setChartType(chartType === 'candle' ? 'line' : 'candle')}
              size="small"
            >
              {chartType === 'candle' ? <LineIcon /> : <CandleIcon />}
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Indicators">
            <IconButton onClick={handleSettingsClick} size="small">
              <SettingsIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Drawing Tools">
            <IconButton size="small">
              <DrawIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}>
            <IconButton onClick={toggleFullscreen} size="small">
              {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      
      <Box ref={chartContainerRef} sx={{ width: '100%', height: 500 }} />
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleSettingsClose}
      >
        <MenuItem onClick={() => { setShowVolume(!showVolume); handleSettingsClose(); }}>
          {showVolume ? '✓' : '  '} Volume
        </MenuItem>
        <MenuItem onClick={() => { setShowMA(!showMA); handleSettingsClose(); }}>
          {showMA ? '✓' : '  '} Moving Averages
        </MenuItem>
        <MenuItem onClick={() => { setShowBB(!showBB); handleSettingsClose(); }}>
          {showBB ? '✓' : '  '} Bollinger Bands
        </MenuItem>
      </Menu>
    </Paper>
  );
};

// Helper functions
function generateMockData(): CandlestickData[] {
  const data: CandlestickData[] = [];
  const now = Math.floor(Date.now() / 1000);
  let basePrice = 180;
  
  for (let i = 100; i >= 0; i--) {
    const time = now - i * 300; // 5-minute intervals
    const change = (Math.random() - 0.5) * 2;
    basePrice += change;
    
    const open = basePrice;
    const close = basePrice + (Math.random() - 0.5) * 1;
    const high = Math.max(open, close) + Math.random() * 0.5;
    const low = Math.min(open, close) - Math.random() * 0.5;
    
    data.push({
      time: time as any,
      open,
      high,
      low,
      close,
    });
  }
  
  return data;
}

function calculateMA(data: CandlestickData[], period: number): LineData[] {
  const ma: LineData[] = [];
  
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    ma.push({
      time: data[i].time,
      value: sum / period,
    });
  }
  
  return ma;
}

function calculateBollingerBands(
  data: CandlestickData[],
  period: number,
  stdDev: number
): { upper: LineData[]; lower: LineData[] } {
  const upper: LineData[] = [];
  const lower: LineData[] = [];
  const ma = calculateMA(data, period);
  
  for (let i = 0; i < ma.length; i++) {
    const dataIndex = i + period - 1;
    let variance = 0;
    
    for (let j = 0; j < period; j++) {
      const diff = data[dataIndex - j].close - ma[i].value;
      variance += diff * diff;
    }
    
    const std = Math.sqrt(variance / period);
    
    upper.push({
      time: ma[i].time,
      value: ma[i].value + std * stdDev,
    });
    
    lower.push({
      time: ma[i].time,
      value: ma[i].value - std * stdDev,
    });
  }
  
  return { upper, lower };
}