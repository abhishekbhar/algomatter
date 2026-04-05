// Mock for lightweight-charts used in Jest tests
export const createChart = jest.fn(() => ({
  addSeries: jest.fn(() => ({
    setData: jest.fn(),
  })),
  applyOptions: jest.fn(),
  timeScale: jest.fn(() => ({
    fitContent: jest.fn(),
  })),
  remove: jest.fn(),
}));

export const AreaSeries = {};
