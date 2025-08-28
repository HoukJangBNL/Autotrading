import React, { useRef, useEffect } from 'react';
import { Box, useTheme } from '@mui/material';
import {
  createChart,
  IChartApi,
  LineData,
  AreaData,
  UTCTimestamp,
  ColorType,
  LineStyle,
} from 'lightweight-charts';

interface MiniChartProps {
  data: Array<{ time: string | number; value: number }>;
  height?: number;
  type?: 'line' | 'area';
  color?: string;
  showGrid?: boolean;
  showAxis?: boolean;
}

export const MiniChart: React.FC<MiniChartProps> = ({
  data,
  height = 60,
  type = 'area',
  color,
  showGrid = false,
  showAxis = false,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const theme = useTheme();

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: theme.palette.text.secondary,
      },
      grid: {
        vertLines: {
          visible: showGrid,
          color: theme.palette.divider,
          style: LineStyle.Dotted,
        },
        horzLines: {
          visible: showGrid,
          color: theme.palette.divider,
          style: LineStyle.Dotted,
        },
      },
      timeScale: {
        visible: showAxis,
        borderVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      rightPriceScale: {
        visible: showAxis,
        borderVisible: false,
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      leftPriceScale: {
        visible: false,
      },
      crosshair: {
        vertLine: {
          visible: false,
        },
        horzLine: {
          visible: false,
        },
      },
      handleScroll: false,
      handleScale: false,
    });

    chartRef.current = chart;

    const chartData = data.map(item => ({
      time: (typeof item.time === 'string' ? new Date(item.time).getTime() / 1000 : item.time) as UTCTimestamp,
      value: item.value,
    }));

    const isPositive = chartData.length > 1 && 
      chartData[chartData.length - 1].value >= chartData[0].value;

    const lineColor = color || (isPositive ? theme.palette.success.main : theme.palette.error.main);

    if (type === 'area') {
      const areaSeries = chart.addAreaSeries({
        topColor: lineColor + '40',
        bottomColor: lineColor + '00',
        lineColor: lineColor,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      areaSeries.setData(chartData as AreaData[]);
    } else {
      const lineSeries = chart.addLineSeries({
        color: lineColor,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      lineSeries.setData(chartData as LineData[]);
    }

    chart.timeScale().fitContent();

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
  }, [data, height, type, color, showGrid, showAxis, theme]);

  return (
    <Box
      ref={chartContainerRef}
      sx={{
        width: '100%',
        height,
        '& > div': {
          position: 'relative !important',
        },
      }}
    />
  );
};