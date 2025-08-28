// Candlestick chart component using TradingView Lightweight Charts

import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
} from 'lightweight-charts';
import { Box, Paper, Typography, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { styled } from '@mui/material/styles';

const ChartContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
}));

const ChartWrapper = styled(Box)({
  flex: 1,
  position: 'relative',
});

interface CandlestickChartProps {
  symbol: string;
  data: CandlestickData[];
  height?: number;
  onTimeframeChange?: (timeframe: string) => void;
  showVolume?: boolean;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  symbol,
  data,
  height = 400,
  onTimeframeChange,
  showVolume = true,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const [timeframe, setTimeframe] = useState('1min');

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { type: 'solid', color: 'white' },
        textColor: 'black',
      },
      grid: {
        vertLines: { color: '#e1e1e1' },
        horzLines: { color: '#e1e1e1' },
      },
      crosshair: {
        mode: 1, // Magnet mode
      },
      timeScale: {
        borderColor: '#cccccc',
      },
    });

    chartRef.current = chart;

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Create volume series if enabled
    if (showVolume) {
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
      volumeSeriesRef.current = volumeSeries;
    }

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [height, showVolume]);

  // Update data
  useEffect(() => {
    if (!candlestickSeriesRef.current) return;

    candlestickSeriesRef.current.setData(data);

    if (showVolume && volumeSeriesRef.current && data.length > 0) {
      const volumeData = data.map((candle) => ({
        time: candle.time,
        value: candle.volume || 0,
        color: candle.close >= candle.open ? '#26a69a' : '#ef5350',
      }));
      volumeSeriesRef.current.setData(volumeData);
    }

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data, showVolume]);

  const handleTimeframeChange = (
    event: React.MouseEvent<HTMLElement>,
    newTimeframe: string | null,
  ) => {
    if (newTimeframe) {
      setTimeframe(newTimeframe);
      onTimeframeChange?.(newTimeframe);
    }
  };

  return (
    <ChartContainer>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">
          {symbol} - {timeframe}
        </Typography>
        <ToggleButtonGroup
          value={timeframe}
          exclusive
          onChange={handleTimeframeChange}
          size="small"
        >
          <ToggleButton value="1min">1m</ToggleButton>
          <ToggleButton value="5min">5m</ToggleButton>
          <ToggleButton value="15min">15m</ToggleButton>
          <ToggleButton value="1hour">1h</ToggleButton>
          <ToggleButton value="1day">1D</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      <ChartWrapper>
        <div ref={chartContainerRef} style={{ width: '100%', height }} />
      </ChartWrapper>
    </ChartContainer>
  );
};