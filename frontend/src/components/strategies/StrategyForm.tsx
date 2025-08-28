import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Grid,
  Stepper,
  Step,
  StepLabel,
  Autocomplete,
  Chip,
  Slider,
  Switch,
  FormControlLabel,
  InputAdornment,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Divider,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { 
  Strategy, 
  StrategyType, 
  StrategyParameter, 
  RiskManagement,
  TradingSchedule 
} from '../../types/strategy';

const steps = ['Basic Info', 'Parameters', 'Risk Management', 'Schedule', 'Review'];

const AVAILABLE_SYMBOLS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM',
  'V', 'JNJ', 'WMT', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'BAC', 'XOM',
];

const TRADING_DAYS = [
  { value: 'MON', label: 'Monday' },
  { value: 'TUE', label: 'Tuesday' },
  { value: 'WED', label: 'Wednesday' },
  { value: 'THU', label: 'Thursday' },
  { value: 'FRI', label: 'Friday' },
];

interface StrategyFormProps {
  strategy?: Strategy;
  onSubmit: (strategy: Partial<Strategy>) => void;
  onCancel: () => void;
}

export const StrategyForm: React.FC<StrategyFormProps> = ({
  strategy,
  onSubmit,
  onCancel,
}) => {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<Partial<Strategy>>({
    name: '',
    description: '',
    type: StrategyType.MOMENTUM,
    symbols: [],
    parameters: [],
    riskManagement: {
      stopLoss: 2,
      takeProfit: 5,
      positionSize: 10,
      maxDrawdown: 10,
      maxPositions: 5,
    },
    schedule: {
      startTime: '09:30',
      endTime: '16:00',
      tradingDays: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
      timezone: 'America/New_York',
    },
    ...strategy,
  });

  const [errors, setErrors] = useState<{ [key: string]: string }>({});

  // Default parameters for each strategy type
  const getDefaultParameters = (type: StrategyType): StrategyParameter[] => {
    switch (type) {
      case StrategyType.MOMENTUM:
        return [
          { name: 'lookbackPeriod', type: 'number', value: 20, min: 5, max: 100, description: 'Number of periods to look back' },
          { name: 'momentumThreshold', type: 'number', value: 0.05, min: 0.01, max: 0.5, step: 0.01, description: 'Minimum momentum to trigger signal' },
          { name: 'useVolume', type: 'boolean', value: true, description: 'Consider volume in momentum calculation' },
        ];
      case StrategyType.MEAN_REVERSION:
        return [
          { name: 'maPeriod', type: 'number', value: 50, min: 10, max: 200, description: 'Moving average period' },
          { name: 'stdDevMultiplier', type: 'number', value: 2, min: 1, max: 3, step: 0.1, description: 'Standard deviation multiplier' },
          { name: 'exitAtMean', type: 'boolean', value: true, description: 'Exit position at mean' },
        ];
      case StrategyType.BREAKOUT:
        return [
          { name: 'breakoutPeriod', type: 'number', value: 20, min: 5, max: 100, description: 'Period for breakout detection' },
          { name: 'confirmationCandles', type: 'number', value: 2, min: 1, max: 5, description: 'Number of confirmation candles' },
          { name: 'volumeIncrease', type: 'number', value: 1.5, min: 1, max: 3, step: 0.1, description: 'Required volume increase' },
        ];
      default:
        return [];
    }
  };

  useEffect(() => {
    if (!strategy && formData.type) {
      setFormData((prev) => ({
        ...prev,
        parameters: getDefaultParameters(formData.type),
      }));
    }
  }, [formData.type, strategy]);

  const handleNext = () => {
    if (validateStep(activeStep)) {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const validateStep = (step: number): boolean => {
    const newErrors: { [key: string]: string } = {};

    switch (step) {
      case 0: // Basic Info
        if (!formData.name) newErrors.name = 'Strategy name is required';
        if (!formData.description) newErrors.description = 'Description is required';
        if (!formData.type) newErrors.type = 'Strategy type is required';
        if (!formData.symbols || formData.symbols.length === 0) {
          newErrors.symbols = 'At least one symbol is required';
        }
        break;
      case 1: // Parameters
        if (!formData.parameters || formData.parameters.length === 0) {
          newErrors.parameters = 'Parameters must be configured';
        }
        break;
      case 2: // Risk Management
        if (!formData.riskManagement?.stopLoss) {
          newErrors.stopLoss = 'Stop loss is required';
        }
        break;
      case 3: // Schedule
        if (!formData.schedule?.tradingDays || formData.schedule.tradingDays.length === 0) {
          newErrors.tradingDays = 'Select at least one trading day';
        }
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (validateStep(4)) {
      onSubmit(formData);
    }
  };

  const handleParameterChange = (index: number, field: string, value: any) => {
    const newParameters = [...(formData.parameters || [])];
    newParameters[index] = { ...newParameters[index], [field]: value };
    setFormData({ ...formData, parameters: newParameters });
  };

  const addParameter = () => {
    const newParameter: StrategyParameter = {
      name: '',
      type: 'number',
      value: 0,
      description: '',
    };
    setFormData({
      ...formData,
      parameters: [...(formData.parameters || []), newParameter],
    });
  };

  const removeParameter = (index: number) => {
    const newParameters = formData.parameters?.filter((_, i) => i !== index);
    setFormData({ ...formData, parameters: newParameters });
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Strategy Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                error={!!errors.name}
                helperText={errors.name}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                error={!!errors.description}
                helperText={errors.description}
                multiline
                rows={3}
                required
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth required error={!!errors.type}>
                <InputLabel>Strategy Type</InputLabel>
                <Select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value as StrategyType })}
                  label="Strategy Type"
                >
                  <MenuItem value={StrategyType.MOMENTUM}>Momentum</MenuItem>
                  <MenuItem value={StrategyType.MEAN_REVERSION}>Mean Reversion</MenuItem>
                  <MenuItem value={StrategyType.BREAKOUT}>Breakout</MenuItem>
                  <MenuItem value={StrategyType.ARBITRAGE}>Arbitrage</MenuItem>
                  <MenuItem value={StrategyType.MARKET_MAKING}>Market Making</MenuItem>
                  <MenuItem value={StrategyType.CUSTOM}>Custom</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <Autocomplete
                multiple
                value={formData.symbols || []}
                onChange={(e, newValue) => setFormData({ ...formData, symbols: newValue })}
                options={AVAILABLE_SYMBOLS}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip variant="outlined" label={option} {...getTagProps({ index })} />
                  ))
                }
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Symbols"
                    error={!!errors.symbols}
                    helperText={errors.symbols}
                    required
                  />
                )}
              />
            </Grid>
          </Grid>
        );

      case 1:
        return (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">Strategy Parameters</Typography>
              <Button startIcon={<AddIcon />} onClick={addParameter}>
                Add Parameter
              </Button>
            </Box>
            {formData.parameters?.map((param, index) => (
              <Accordion key={index} defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography>{param.name || `Parameter ${index + 1}`}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={4}>
                      <TextField
                        fullWidth
                        label="Name"
                        value={param.name}
                        onChange={(e) => handleParameterChange(index, 'name', e.target.value)}
                      />
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <FormControl fullWidth>
                        <InputLabel>Type</InputLabel>
                        <Select
                          value={param.type}
                          onChange={(e) => handleParameterChange(index, 'type', e.target.value)}
                          label="Type"
                        >
                          <MenuItem value="number">Number</MenuItem>
                          <MenuItem value="string">String</MenuItem>
                          <MenuItem value="boolean">Boolean</MenuItem>
                          <MenuItem value="select">Select</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      {param.type === 'number' ? (
                        <TextField
                          fullWidth
                          label="Value"
                          type="number"
                          value={param.value}
                          onChange={(e) => handleParameterChange(index, 'value', parseFloat(e.target.value))}
                        />
                      ) : param.type === 'boolean' ? (
                        <FormControlLabel
                          control={
                            <Switch
                              checked={param.value}
                              onChange={(e) => handleParameterChange(index, 'value', e.target.checked)}
                            />
                          }
                          label="Enabled"
                        />
                      ) : (
                        <TextField
                          fullWidth
                          label="Value"
                          value={param.value}
                          onChange={(e) => handleParameterChange(index, 'value', e.target.value)}
                        />
                      )}
                    </Grid>
                    {param.type === 'number' && (
                      <>
                        <Grid item xs={12} md={3}>
                          <TextField
                            fullWidth
                            label="Min"
                            type="number"
                            value={param.min || ''}
                            onChange={(e) => handleParameterChange(index, 'min', parseFloat(e.target.value))}
                          />
                        </Grid>
                        <Grid item xs={12} md={3}>
                          <TextField
                            fullWidth
                            label="Max"
                            type="number"
                            value={param.max || ''}
                            onChange={(e) => handleParameterChange(index, 'max', parseFloat(e.target.value))}
                          />
                        </Grid>
                        <Grid item xs={12} md={3}>
                          <TextField
                            fullWidth
                            label="Step"
                            type="number"
                            value={param.step || ''}
                            onChange={(e) => handleParameterChange(index, 'step', parseFloat(e.target.value))}
                          />
                        </Grid>
                      </>
                    )}
                    <Grid item xs={12} md={param.type === 'number' ? 3 : 12}>
                      <TextField
                        fullWidth
                        label="Description"
                        value={param.description || ''}
                        onChange={(e) => handleParameterChange(index, 'description', e.target.value)}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <Button
                        color="error"
                        startIcon={<DeleteIcon />}
                        onClick={() => removeParameter(index)}
                      >
                        Remove
                      </Button>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        );

      case 2:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Risk Management Settings
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Stop Loss (%)</Typography>
              <Slider
                value={formData.riskManagement?.stopLoss || 0}
                onChange={(e, value) => setFormData({
                  ...formData,
                  riskManagement: { ...formData.riskManagement!, stopLoss: value as number },
                })}
                min={0.5}
                max={10}
                step={0.5}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Take Profit (%)</Typography>
              <Slider
                value={formData.riskManagement?.takeProfit || 0}
                onChange={(e, value) => setFormData({
                  ...formData,
                  riskManagement: { ...formData.riskManagement!, takeProfit: value as number },
                })}
                min={1}
                max={20}
                step={0.5}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Position Size (% of capital)</Typography>
              <Slider
                value={formData.riskManagement?.positionSize || 0}
                onChange={(e, value) => setFormData({
                  ...formData,
                  riskManagement: { ...formData.riskManagement!, positionSize: value as number },
                })}
                min={1}
                max={50}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Max Drawdown (%)</Typography>
              <Slider
                value={formData.riskManagement?.maxDrawdown || 0}
                onChange={(e, value) => setFormData({
                  ...formData,
                  riskManagement: { ...formData.riskManagement!, maxDrawdown: value as number },
                })}
                min={5}
                max={30}
                step={1}
                marks
                valueLabelDisplay="auto"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Max Concurrent Positions"
                type="number"
                value={formData.riskManagement?.maxPositions || 0}
                onChange={(e) => setFormData({
                  ...formData,
                  riskManagement: { ...formData.riskManagement!, maxPositions: parseInt(e.target.value) },
                })}
                InputProps={{ inputProps: { min: 1, max: 20 } }}
              />
            </Grid>
          </Grid>
        );

      case 3:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Trading Schedule
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <TimePicker
                  label="Start Time"
                  value={new Date(`2000-01-01T${formData.schedule?.startTime || '09:30'}`)}
                  onChange={(newValue) => {
                    if (newValue) {
                      const time = `${newValue.getHours().toString().padStart(2, '0')}:${newValue.getMinutes().toString().padStart(2, '0')}`;
                      setFormData({
                        ...formData,
                        schedule: { ...formData.schedule!, startTime: time },
                      });
                    }
                  }}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </LocalizationProvider>
            </Grid>
            <Grid item xs={12} md={6}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <TimePicker
                  label="End Time"
                  value={new Date(`2000-01-01T${formData.schedule?.endTime || '16:00'}`)}
                  onChange={(newValue) => {
                    if (newValue) {
                      const time = `${newValue.getHours().toString().padStart(2, '0')}:${newValue.getMinutes().toString().padStart(2, '0')}`;
                      setFormData({
                        ...formData,
                        schedule: { ...formData.schedule!, endTime: time },
                      });
                    }
                  }}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </LocalizationProvider>
            </Grid>
            <Grid item xs={12}>
              <Typography gutterBottom>Trading Days</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {TRADING_DAYS.map((day) => (
                  <Chip
                    key={day.value}
                    label={day.label}
                    onClick={() => {
                      const days = formData.schedule?.tradingDays || [];
                      if (days.includes(day.value)) {
                        setFormData({
                          ...formData,
                          schedule: {
                            ...formData.schedule!,
                            tradingDays: days.filter((d) => d !== day.value),
                          },
                        });
                      } else {
                        setFormData({
                          ...formData,
                          schedule: {
                            ...formData.schedule!,
                            tradingDays: [...days, day.value],
                          },
                        });
                      }
                    }}
                    color={formData.schedule?.tradingDays?.includes(day.value) ? 'primary' : 'default'}
                    variant={formData.schedule?.tradingDays?.includes(day.value) ? 'filled' : 'outlined'}
                  />
                ))}
              </Box>
              {errors.tradingDays && (
                <Typography variant="caption" color="error">
                  {errors.tradingDays}
                </Typography>
              )}
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Timezone"
                value={formData.schedule?.timezone || 'America/New_York'}
                onChange={(e) => setFormData({
                  ...formData,
                  schedule: { ...formData.schedule!, timezone: e.target.value },
                })}
                select
              >
                <MenuItem value="America/New_York">Eastern Time (ET)</MenuItem>
                <MenuItem value="America/Chicago">Central Time (CT)</MenuItem>
                <MenuItem value="America/Denver">Mountain Time (MT)</MenuItem>
                <MenuItem value="America/Los_Angeles">Pacific Time (PT)</MenuItem>
                <MenuItem value="UTC">UTC</MenuItem>
              </TextField>
            </Grid>
          </Grid>
        );

      case 4:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review Strategy Configuration
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Please review your strategy configuration before submitting.
                </Alert>
              </Grid>
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Basic Information
                  </Typography>
                  <Typography><strong>Name:</strong> {formData.name}</Typography>
                  <Typography><strong>Type:</strong> {formData.type}</Typography>
                  <Typography><strong>Symbols:</strong> {formData.symbols?.join(', ')}</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Risk Management
                  </Typography>
                  <Typography><strong>Stop Loss:</strong> {formData.riskManagement?.stopLoss}%</Typography>
                  <Typography><strong>Take Profit:</strong> {formData.riskManagement?.takeProfit}%</Typography>
                  <Typography><strong>Position Size:</strong> {formData.riskManagement?.positionSize}%</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Trading Schedule
                  </Typography>
                  <Typography>
                    <strong>Hours:</strong> {formData.schedule?.startTime} - {formData.schedule?.endTime}
                  </Typography>
                  <Typography>
                    <strong>Days:</strong> {formData.schedule?.tradingDays?.join(', ')}
                  </Typography>
                  <Typography>
                    <strong>Timezone:</strong> {formData.schedule?.timezone}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Parameters ({formData.parameters?.length})
                  </Typography>
                  {formData.parameters?.map((param, index) => (
                    <Typography key={index}>
                      <strong>{param.name}:</strong> {param.value} ({param.type})
                    </Typography>
                  ))}
                </Paper>
              </Grid>
            </Grid>
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Box sx={{ minHeight: 400 }}>
        {renderStepContent(activeStep)}
      </Box>

      <Divider sx={{ my: 3 }} />

      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button
          onClick={onCancel}
          startIcon={<CancelIcon />}
        >
          Cancel
        </Button>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
          >
            Back
          </Button>
          {activeStep < steps.length - 1 ? (
            <Button
              variant="contained"
              onClick={handleNext}
            >
              Next
            </Button>
          ) : (
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              startIcon={<SaveIcon />}
            >
              {strategy ? 'Update' : 'Create'} Strategy
            </Button>
          )}
        </Box>
      </Box>
    </Paper>
  );
};