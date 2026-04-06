// Mock for lightweight-charts used in Jest tests
export const createChart = jest.fn(() => ({
  addSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
    applyOptions: jest.fn(),
  })),
  applyOptions: jest.fn(),
  timeScale: jest.fn(() => ({
    fitContent: jest.fn(),
  })),
  priceScale: jest.fn(() => ({
    applyOptions: jest.fn(),
  })),
  remove: jest.fn(),
}));

export const AreaSeries = {};
export const CandlestickSeries = {};
export const HistogramSeries = {};
export const ColorType = { Solid: "solid", VerticalGradient: "gradient" };
