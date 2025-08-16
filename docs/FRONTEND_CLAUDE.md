# ASX200 Trading System - Frontend Development Guide

## Project Overview

**Project Name**: ASX200 Trading Dashboard Frontend  
**Purpose**: Real-time web interface for monitoring automated algorithmic trading system  
**Target User**: Professional day-trader requiring minimal-maintenance oversight  
**Primary Goal**: Provide comprehensive, real-time visibility into trading operations with minimal cognitive load  

### Key Interface Requirements
- **Real-time Performance**: Live P&L, positions, and market data updates
- **Risk Monitoring**: Clear visibility into exposure limits and current risk
- **Strategy Oversight**: Performance tracking and strategy health monitoring  
- **System Health**: Operational status and alert management
- **Historical Analysis**: Performance attribution and backtesting results
- **Mobile Access**: Responsive design for on-the-go monitoring

## Technical Stack

### Core Technologies
- **Framework**: Next.js 14+ with App Router
- **Language**: TypeScript 5+
- **Styling**: Tailwind CSS 3+ with custom trading theme
- **Charts**: Recharts + TradingView Lightweight Charts
- **State Management**: Zustand with real-time subscriptions
- **API Client**: Custom fetch wrapper with auto-retry
- **Real-time**: Server-Sent Events (SSE) + WebSocket fallback
- **Authentication**: NextAuth.js with JWT integration
- **Testing**: Jest + React Testing Library + Playwright E2E

### Why These Choices
- **Next.js 14**: App Router provides excellent UX with Server Components
- **TypeScript**: Essential for financial data type safety and error prevention
- **Tailwind**: Rapid development with consistent design system
- **Recharts**: Performance and customization for financial charts
- **Zustand**: Lightweight state management with excellent TypeScript support
- **SSE**: Efficient real-time updates with automatic reconnection

## Application Architecture

```
frontend/
├── app/                          # Next.js 14 App Router
│   ├── (auth)/                  # Auth route group
│   │   ├── login/               # Login page
│   │   └── layout.tsx           # Auth layout
│   ├── (dashboard)/             # Protected dashboard routes  
│   │   ├── dashboard/           # Main dashboard
│   │   │   ├── page.tsx
│   │   │   └── loading.tsx
│   │   ├── portfolio/           # Portfolio management
│   │   │   ├── page.tsx
│   │   │   ├── [positionId]/    # Individual position details
│   │   │   └── components/      # Portfolio-specific components
│   │   ├── strategies/          # Strategy monitoring
│   │   │   ├── page.tsx
│   │   │   ├── [strategyId]/    # Strategy details
│   │   │   └── components/
│   │   ├── risk/                # Risk management
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   ├── analytics/           # Historical analysis
│   │   │   ├── page.tsx
│   │   │   ├── backtest/        # Backtesting results
│   │   │   ├── performance/     # Performance attribution
│   │   │   └── components/
│   │   ├── health/              # System monitoring
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   ├── settings/            # Configuration
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   └── layout.tsx           # Dashboard layout with nav
│   ├── api/                     # API routes (proxy/middleware)
│   │   ├── auth/                # Authentication endpoints
│   │   └── proxy/               # Backend API proxy
│   ├── globals.css              # Global styles and CSS variables
│   ├── layout.tsx               # Root layout
│   ├── loading.tsx              # Global loading UI
│   ├── error.tsx                # Global error UI
│   └── not-found.tsx            # 404 page
├── components/                   # Reusable UI components
│   ├── ui/                      # Base UI components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── table.tsx
│   │   ├── alert.tsx
│   │   ├── badge.tsx
│   │   ├── skeleton.tsx
│   │   └── index.ts
│   ├── charts/                  # Financial chart components
│   │   ├── LineChart.tsx        # Price/performance line charts
│   │   ├── CandlestickChart.tsx # OHLC candlestick charts
│   │   ├── BarChart.tsx         # Volume and metrics
│   │   ├── HeatMap.tsx          # Correlation/risk heatmaps
│   │   ├── Sparkline.tsx        # Mini trend indicators
│   │   └── ChartContainer.tsx   # Wrapper with controls
│   ├── trading/                 # Trading-specific components
│   │   ├── PositionCard.tsx     # Individual position display
│   │   ├── PositionTable.tsx    # Positions overview table
│   │   ├── OrderBook.tsx        # Order status display
│   │   ├── PnLDisplay.tsx       # P&L with color coding
│   │   ├── RiskGauge.tsx        # Risk level indicators
│   │   ├── StrategyCard.tsx     # Strategy performance card
│   │   └── SignalIndicator.tsx  # Trading signal display
│   ├── dashboard/               # Dashboard-specific components
│   │   ├── MetricCard.tsx       # Key metric display cards
│   │   ├── AlertPanel.tsx       # System alerts display
│   │   ├── QuickStats.tsx       # Summary statistics
│   │   ├── MarketOverview.tsx   # Market status overview
│   │   └── RecentActivity.tsx   # Recent trades/signals
│   ├── layout/                  # Layout components
│   │   ├── Navigation.tsx       # Main navigation bar
│   │   ├── Sidebar.tsx          # Collapsible sidebar
│   │   ├── Header.tsx           # Page headers
│   │   ├── Footer.tsx           # Footer with status
│   │   └── MobileNav.tsx        # Mobile navigation
│   └── common/                  # Common reusable components
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       ├── DataTable.tsx
│       ├── FilterPanel.tsx
│       ├── DateRangePicker.tsx
│       ├── SearchInput.tsx
│       └── NotificationToast.tsx
├── lib/                         # Utility libraries and configurations
│   ├── api/                     # API client and types
│   │   ├── client.ts            # Main API client
│   │   ├── endpoints.ts         # API endpoint definitions
│   │   ├── types.ts             # API response types
│   │   ├── realtime.ts          # Real-time connection manager
│   │   └── error-handling.ts    # API error handling
│   ├── auth/                    # Authentication utilities
│   │   ├── config.ts            # NextAuth configuration
│   │   ├── providers.ts         # Auth providers
│   │   └── middleware.ts        # Auth middleware
│   ├── stores/                  # Zustand stores
│   │   ├── usePortfolioStore.ts # Portfolio state management
│   │   ├── useRiskStore.ts      # Risk metrics state
│   │   ├── useMarketStore.ts    # Market data state
│   │   ├── useUIStore.ts        # UI state (filters, preferences)
│   │   └── useRealtimeStore.ts  # Real-time data subscriptions
│   ├── utils/                   # Utility functions
│   │   ├── formatters.ts        # Number/currency/date formatting
│   │   ├── calculations.ts      # Financial calculations
│   │   ├── validators.ts        # Input validation
│   │   ├── constants.ts         # App constants
│   │   ├── helpers.ts           # General helper functions
│   │   └── cn.ts                # Tailwind class utilities
│   ├── hooks/                   # Custom React hooks
│   │   ├── useRealtime.ts       # Real-time data subscription
│   │   ├── usePortfolio.ts      # Portfolio data fetching
│   │   ├── useMarketData.ts     # Market data management
│   │   ├── useLocalStorage.ts   # Persistent local state
│   │   ├── useDebounce.ts       # Input debouncing
│   │   └── useWebSocket.ts      # WebSocket connection
│   └── types/                   # TypeScript type definitions
│       ├── api.ts               # API response types
│       ├── trading.ts           # Trading-related types
│       ├── portfolio.ts         # Portfolio types
│       ├── risk.ts              # Risk management types
│       └── ui.ts                # UI component types
├── styles/                      # Styling and themes
│   ├── globals.css              # Global styles
│   ├── components.css           # Component-specific styles
│   └── themes/                  # Theme configurations
│       ├── trading-dark.ts      # Dark theme for trading
│       ├── trading-light.ts     # Light theme alternative
│       └── colors.ts            # Color palette definitions
├── public/                      # Static assets
│   ├── icons/                   # Custom trading icons
│   ├── images/                  # Images and logos
│   └── manifest.json            # PWA manifest
├── __tests__/                   # Test files
│   ├── components/              # Component tests
│   ├── pages/                   # Page tests
│   ├── hooks/                   # Hook tests
│   ├── utils/                   # Utility tests
│   └── e2e/                     # End-to-end tests
├── docs/                        # Documentation
│   ├── components.md            # Component documentation
│   ├── api-integration.md       # API integration guide
│   └── deployment.md            # Deployment instructions
├── package.json
├── tailwind.config.js
├── next.config.js
├── tsconfig.json
├── jest.config.js
├── playwright.config.ts
└── README.md
```

## Design System & UI/UX

### Color Palette (Trading Theme)
```typescript
// styles/themes/trading-dark.ts
export const tradingDarkTheme = {
  colors: {
    // Background colors
    background: {
      primary: '#0a0a0a',        // Main background
      secondary: '#1a1a1a',      // Card backgrounds
      tertiary: '#2a2a2a',       // Elevated elements
    },
    
    // Text colors
    text: {
      primary: '#ffffff',        // Primary text
      secondary: '#a1a1aa',      // Secondary text
      muted: '#71717a',          // Muted text
    },
    
    // Trading-specific colors
    trading: {
      profit: '#22c55e',         // Green for profits
      loss: '#ef4444',           // Red for losses
      neutral: '#6b7280',        // Gray for neutral
      buy: '#10b981',            // Buy signal color
      sell: '#f59e0b',           // Sell signal color
      warning: '#f59e0b',        // Warning alerts
      danger: '#dc2626',         // Danger/risk alerts
    },
    
    // Chart colors
    chart: {
      primary: '#3b82f6',        // Primary chart line
      secondary: '#8b5cf6',      // Secondary metrics
      volume: '#6b7280',         // Volume bars
      grid: '#374151',           // Chart grid lines
    },
    
    // UI element colors
    border: '#374151',           // Border color
    ring: '#3b82f6',            // Focus ring color
  }
}
```

### Typography Scale
```typescript
// Font hierarchy for financial data
export const typography = {
  // Large numbers (portfolio value, P&L)
  display: 'text-4xl font-bold tracking-tight',
  
  // Section headings
  heading: 'text-2xl font-semibold',
  
  // Card titles
  title: 'text-lg font-medium',
  
  // Table headers
  label: 'text-sm font-medium text-gray-400',
  
  // Data values
  value: 'text-base font-mono',
  
  // Small metadata
  caption: 'text-xs text-gray-500',
}
```

### Component Design Principles
1. **Data Density**: Maximize information per screen real estate
2. **Scannable Layout**: Easy to quickly identify key metrics
3. **Color Coding**: Consistent use of red/green for performance
4. **Monospace Numbers**: All financial figures use monospace fonts
5. **Real-time Feedback**: Live data updates with smooth animations
6. **Professional Aesthetics**: Clean, Bloomberg-terminal inspired design

## Page-by-Page Specifications

### 1. Dashboard Page (`/dashboard`)
**Purpose**: Single-pane overview of entire trading operation

**Layout Structure**:
```typescript
interface DashboardLayout {
  topBar: {
    portfolioValue: number;
    dailyPnL: number;
    totalReturn: number;
    activePositions: number;
  };
  
  leftColumn: {
    positionsSummary: Position[];
    recentSignals: Signal[];
    systemHealth: HealthMetric[];
  };
  
  centerColumn: {
    portfolioChart: ChartData;
    performanceMetrics: Metric[];
  };
  
  rightColumn: {
    riskMetrics: RiskData;
    marketOverview: MarketData;
    alerts: Alert[];
  };
}
```

**Key Components**:
- **Portfolio Value Card**: Large, prominent display with 24h change
- **Active Positions Grid**: 3x2 grid showing current positions
- **Performance Chart**: Portfolio value over time with strategy overlays
- **Risk Dashboard**: Current exposure vs limits with progress bars
- **Alert Panel**: System notifications and trading alerts
- **Market Status**: ASX market hours and overall market sentiment

**Real-time Updates**:
- Portfolio value (every 5 seconds during market hours)
- Position P&L (real-time)
- New trading signals (immediate)
- Risk metrics (every 30 seconds)

### 2. Portfolio Page (`/portfolio`)
**Purpose**: Detailed position management and P&L analysis

**Features**:
- **Positions Table**: Sortable table with all open positions
- **Position Details**: Drill-down to individual position analysis
- **P&L Analytics**: Performance attribution by position/strategy
- **Order History**: Recent orders and execution details
- **Position Sizing Analysis**: Current vs optimal position sizes

**Table Columns**:
```typescript
interface PositionTableRow {
  symbol: string;
  strategy: string;
  side: 'LONG' | 'SHORT';
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  dayPnL: number;
  positionValue: number;
  duration: string; // "3d 4h"
  stopLoss?: number;
  takeProfit?: number;
}
```

### 3. Strategies Page (`/strategies`)
**Purpose**: Monitor and analyze trading strategy performance

**Strategy Card Layout**:
```typescript
interface StrategyCard {
  name: string;
  status: 'ACTIVE' | 'PAUSED' | 'STOPPED';
  totalReturn: number;
  sharpeRatio: number;
  winRate: number;
  activePositions: number;
  maxDrawdown: number;
  avgHoldingPeriod: string;
  lastSignal: Date;
  performanceChart: ChartData;
}
```

**Features**:
- **Strategy Performance Grid**: Cards for each strategy
- **Comparative Analysis**: Side-by-side strategy comparison
- **Signal History**: Recent signals by strategy
- **Backtest Results**: Historical performance validation
- **Strategy Settings**: Configuration (view-only with override capabilities)

### 4. Risk Management Page (`/risk`)
**Purpose**: Comprehensive risk monitoring and control

**Risk Metrics Display**:
```typescript
interface RiskDashboard {
  portfolioRisk: {
    totalExposure: number;
    maxExposureLimit: number;
    currentDrawdown: number;
    maxDrawdownLimit: number;
    var95: number; // Value at Risk
    correlationRisk: number;
  };
  
  positionRisk: {
    largestPosition: number;
    positionConcentration: number;
    sectorExposure: SectorBreakdown[];
    leverageRatio: number;
  };
  
  systemRisk: {
    dailyLossLimit: number;
    dailyLossUsed: number;
    consecutiveLosses: number;
    riskBudgetRemaining: number;
  };
}
```

**Visual Components**:
- **Risk Gauges**: Circular progress indicators for key limits
- **Exposure Heatmap**: Visual representation of sector/position concentration
- **Correlation Matrix**: Position correlation visualization
- **Risk Timeline**: Historical risk metrics over time

### 5. Analytics Page (`/analytics`)
**Purpose**: Deep historical analysis and performance attribution

**Analysis Modules**:
- **Performance Attribution**: Returns broken down by strategy/time period
- **Backtest Comparison**: Live vs backtested performance
- **Risk-Adjusted Returns**: Sharpe, Sortino, Calmar ratios
- **Trade Analysis**: Win/loss patterns and optimization opportunities
- **Market Regime Analysis**: Performance across different market conditions

### 6. System Health Page (`/health`)
**Purpose**: Operational monitoring and system diagnostics

**Health Metrics**:
```typescript
interface SystemHealth {
  connectivity: {
    ibkrConnection: 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';
    databaseStatus: 'HEALTHY' | 'DEGRADED' | 'DOWN';
    redisStatus: 'HEALTHY' | 'DEGRADED' | 'DOWN';
    lastDataUpdate: Date;
  };
  
  performance: {
    apiResponseTime: number;
    signalLatency: number;
    orderExecutionTime: number;
    systemUptime: string;
  };
  
  dataQuality: {
    missingDataPoints: number;
    priceAnomalies: number;
    lastValidation: Date;
  };
}
```

## Real-Time Data Architecture

### WebSocket/SSE Integration
```typescript
// lib/realtime/connection-manager.ts
export class RealtimeConnectionManager {
  private eventSource: EventSource | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  
  connect(subscriptions: Subscription[]) {
    // Establish SSE connection to FastAPI backend
    // Handle automatic reconnection
    // Manage subscription lifecycle
  }
  
  subscribe(topic: RealtimeTopic, callback: (data: any) => void) {
    // Subscribe to specific data streams
    // Portfolio updates, market data, system events
  }
}

// Real-time data topics
export enum RealtimeTopic {
  PORTFOLIO_UPDATE = 'portfolio_update',
  POSITION_UPDATE = 'position_update', 
  MARKET_DATA = 'market_data',
  TRADING_SIGNAL = 'trading_signal',
  RISK_ALERT = 'risk_alert',
  SYSTEM_STATUS = 'system_status'
}
```

### State Management with Real-time Updates
```typescript
// lib/stores/useRealtimeStore.ts
export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  connectionStatus: 'disconnected',
  subscriptions: new Map(),
  
  connect: () => {
    const manager = new RealtimeConnectionManager();
    manager.connect(Array.from(get().subscriptions.keys()));
  },
  
  subscribe: (topic: RealtimeTopic, callback: Function) => {
    // Add subscription and callback
    // Auto-connect if not already connected
  },
  
  updatePortfolio: (data: PortfolioUpdate) => {
    // Update portfolio store with real-time data
    usePortfolioStore.getState().updateFromRealtime(data);
  }
}));
```

## API Integration

### Backend API Client
```typescript
// lib/api/client.ts
export class TradingAPIClient {
  private baseURL: string;
  private authToken: string | null = null;
  
  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }
  
  // Portfolio endpoints
  async getPortfolio(): Promise<Portfolio> {
    return this.request('/api/portfolio');
  }
  
  async getPositions(): Promise<Position[]> {
    return this.request('/api/portfolio/positions');
  }
  
  // Strategy endpoints  
  async getStrategies(): Promise<Strategy[]> {
    return this.request('/api/strategies');
  }
  
  async getStrategyPerformance(strategyId: string): Promise<StrategyPerformance> {
    return this.request(`/api/strategies/${strategyId}/performance`);
  }
  
  // Risk endpoints
  async getRiskMetrics(): Promise<RiskMetrics> {
    return this.request('/api/risk/metrics');
  }
  
  // System health endpoints
  async getSystemHealth(): Promise<SystemHealth> {
    return this.request('/api/health');
  }
  
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    // Implement request with auth, retries, error handling
  }
}
```

### Type Definitions
```typescript
// lib/types/trading.ts
export interface Portfolio {
  totalValue: number;
  cashBalance: number;
  totalInvested: number;
  totalPnL: number;
  dailyPnL: number;
  totalReturn: number;
  positions: Position[];
  lastUpdated: Date;
}

export interface Position {
  id: string;
  symbol: string;
  strategy: string;
  side: 'LONG' | 'SHORT';
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  realizedPnL: number;
  positionValue: number;
  stopLoss?: number;
  takeProfit?: number;
  openedAt: Date;
  duration: number; // seconds
}

export interface Strategy {
  id: string;
  name: string;
  status: 'ACTIVE' | 'PAUSED' | 'STOPPED';
  totalReturn: number;
  sharpeRatio: number;
  winRate: number;
  activePositions: number;
  maxDrawdown: number;
  avgHoldingPeriod: number;
  lastSignal?: Date;
}

export interface RiskMetrics {
  totalExposure: number;
  maxExposureLimit: number;
  currentDrawdown: number;
  maxDrawdownLimit: number;
  var95: number;
  portfolioVaR: number;
  concentrationRisk: number;
  correlationRisk: number;
  dailyLossLimit: number;
  dailyLossUsed: number;
}
```

## Performance Optimization

### Code Splitting and Lazy Loading
```typescript
// Dynamic imports for heavy components
const AdvancedChart = dynamic(() => import('@/components/charts/AdvancedChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false
});

const PortfolioAnalytics = dynamic(() => import('@/components/analytics/PortfolioAnalytics'), {
  loading: () => <AnalyticsSkeleton />
});
```

### Data Caching Strategy
```typescript
// lib/hooks/usePortfolio.ts
export function usePortfolio() {
  return useSWR('/api/portfolio', apiClient.getPortfolio, {
    refreshInterval: 5000, // 5 second refresh during market hours
    revalidateOnFocus: true,
    dedupingInterval: 2000, // Prevent duplicate requests
    errorRetryCount: 3,
    onError: (error) => {
      // Handle API errors gracefully
      toast.error('Failed to load portfolio data');
    }
  });
}
```

### Chart Performance
```typescript
// Virtualized large datasets
export function PositionTable({ positions }: { positions: Position[] }) {
  const { scrollElementRef, wrapperProps, virtualItems } = useVirtualizer({
    count: positions.length,
    scrollElementRef: tableRef,
    estimateSize: () => 48, // Row height
    overscan: 10
  });
  
  return (
    <div {...wrapperProps}>
      {virtualItems.map((virtualItem) => (
        <PositionRow 
          key={virtualItem.index}
          position={positions[virtualItem.index]}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            transform: `translateY(${virtualItem.start}px)`
          }}
        />
      ))}
    </div>
  );
}
```

## Mobile Responsive Design

### Breakpoint Strategy
```typescript
// tailwind.config.js
module.exports = {
  theme: {
    screens: {
      'xs': '475px',   // Large phones
      'sm': '640px',   // Small tablets
      'md': '768px',   // Tablets
      'lg': '1024px',  // Laptops
      'xl': '1280px',  // Desktops
      '2xl': '1536px', // Large desktops
    }
  }
}
```

### Mobile-First Components
```typescript
// Mobile-optimized dashboard layout
export function MobileDashboard() {
  return (
    <div className="space-y-4 p-4">
      {/* Swipeable metric cards */}
      <MetricCarousel metrics={portfolioMetrics} />
      
      {/* Collapsible positions list */}
      <CollapsiblePositions positions={positions} />
      
      {/* Bottom navigation for quick actions */}
      <MobileQuickActions />
    </div>
  );
}
```

## Testing Strategy

### Component Testing
```typescript
// __tests__/components/PositionCard.test.tsx
describe('PositionCard', () => {
  it('displays profit in green', () => {
    const position = createMockPosition({ unrealizedPnL: 1500 });
    render(<PositionCard position={position} />);
    
    expect(screen.getByText('+$1,500.00')).toHaveClass('text-green-500');
  });
  
  it('displays loss in red', () => {
    const position = createMockPosition({ unrealizedPnL: -750 });
    render(<PositionCard position={position} />);
    
    expect(screen.getByText('-$750.00')).toHaveClass('text-red-500');
  });
});
```

### E2E Testing
```typescript
// __tests__/e2e/trading-flow.spec.ts
test('user can monitor portfolio performance', async ({ page }) => {
  await page.goto('/dashboard');
  
  // Check portfolio value is displayed
  await expect(page.locator('[data-testid="portfolio-value"]')).toBeVisible();
  
  // Navigate to portfolio page
  await page.click('[data-testid="nav-portfolio"]');
  await expect(page).toHaveURL('/portfolio');
  
  // Verify positions table loads
  await expect(page.locator('[data-testid="positions-table"]')).toBeVisible();
  
  // Check real-time updates work
  await page.waitForSelector('[data-testid="last-updated"]');
});
```

## Security Implementation

### Authentication Flow
```typescript
// lib/auth/config.ts
export const authConfig: NextAuthConfig = {
  providers: [
    Credentials({
      credentials: {
        email: { type: 'email' },
        password: { type: 'password' }
      },
      authorize: async (credentials) => {
        // Validate against FastAPI backend
        const response = await fetch(`${process.env.API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(credentials)
        });
        
        if (response.ok) {
          const user = await response.json();
          return { id: user.id, email: user.email, token: user.access_token };
        }
        return null;
      }
    })
  ],
  pages: {
    signIn: '/login',
    error: '/auth/error'
  },
  callbacks: {
    jwt: ({ token, user }) => {
      if (user) token.accessToken = user.token;
      return token;
    },
    session: ({ session, token }) => {
      session.accessToken = token.accessToken;
      return session;
    }
  }
};
```

### Route Protection
```typescript
// app/(dashboard)/layout.tsx
export default async function DashboardLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authConfig);
  
  if (!session) {
    redirect('/login');
  }
  
  return (
    <div className="min-h-screen bg-gray-900">
      <Navigation />
      <main className="pl-64 pt-16">
        {children}
      </main>
    </div>
  );
}
```

## Deployment Configuration

### Environment Variables
```typescript
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    API_URL: process.env.API_URL,
    WS_URL: process.env.WS_URL,
    NEXTAUTH_URL: process.env.NEXTAUTH_URL,
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
  },
  
  // Performance optimizations
  experimental: {
    optimizeCss: true,
    swcMinify: true,
  },
  
  // PWA configuration
  pwa: {
    dest: 'public',
    register: true,
    skipWaiting: true,
    disable: process.env.NODE_ENV === 'development'
  }
};
```

### Docker Configuration
```dockerfile
# Dockerfile
FROM node:18-alpine AS base

# Dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Builder
FROM base AS builder
WORKDIR /app
COPY . .
COPY --from=deps /app/node_modules ./node_modules
RUN npm run build

# Runner
FROM base AS runner
WORKDIR /app
ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
```

## Development Workflow

### Development Commands
```json
// package.json scripts
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "lint:fix": "next lint --fix",
    "type-check": "tsc --noEmit",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "analyze": "cross-env ANALYZE=true next build"
  }
}
```

### Code Quality Tools
```typescript
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "@typescript-eslint/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "react-hooks/exhaustive-deps": "error"
  }
}
```

## Performance Targets

### Core Web Vitals
- **First Contentful Paint**: <1.5s
- **Largest Contentful Paint**: <2.5s
- **Cumulative Layout Shift**: <0.1
- **First Input Delay**: <100ms

### Application Performance
- **Dashboard Load Time**: <2s (initial load)
- **Page Navigation**: <500ms
- **Real-time Update Latency**: <100ms
- **Chart Rendering**: <1s for complex charts
- **API Response Handling**: <200ms processing time

### Bundle Size Targets
- **Initial Bundle**: <250KB gzipped
- **Total JavaScript**: <1MB
- **Route-level Code Splitting**: <100KB per route
- **Image Optimization**: WebP format, lazy loading

## Progressive Web App Features

### Service Worker Strategy
```typescript
// public/sw.js - Service Worker for offline support
self.addEventListener('fetch', (event) => {
  // Cache trading data for offline viewing
  if (event.request.url.includes('/api/portfolio')) {
    event.respondWith(
      caches.open('trading-data').then(cache => {
        return cache.match(event.request).then(response => {
          // Return cached data if offline
          return response || fetch(event.request);
        });
      })
    );
  }
});
```

### Offline Capabilities
- **Portfolio Snapshot**: Cache last known portfolio state
- **Historical Data**: Cache charts and performance data  
- **Read-only Mode**: Display cached data when API unavailable
- **Sync on Reconnect**: Update cached data when connection restored

## Accessibility Requirements

### WCAG 2.1 AA Compliance
- **Keyboard Navigation**: Full keyboard support for all interactions
- **Screen Reader Support**: Proper ARIA labels for financial data
- **Color Contrast**: Minimum 4.5:1 ratio for all text
- **Focus Management**: Clear focus indicators and logical tab order
- **Alternative Text**: Descriptive alt text for charts and icons

### Financial Data Accessibility
```typescript
// Accessible financial data display
export function AccessiblePnLDisplay({ value, label }: PnLProps) {
  const isProfit = value >= 0;
  
  return (
    <div
      role="group"
      aria-labelledby={`${label}-label`}
      aria-describedby={`${label}-value`}
    >
      <div id={`${label}-label`} className="sr-only">
        {label}
      </div>
      <div
        id={`${label}-value`}
        className={cn(
          'text-2xl font-mono',
          isProfit ? 'text-green-500' : 'text-red-500'
        )}
        aria-label={`${label}: ${isProfit ? 'profit' : 'loss'} of ${formatCurrency(value)}`}
      >
        {formatCurrency(value)}
      </div>
    </div>
  );
}
```

## Final Implementation Notes

### Development Priorities
1. **Core Dashboard**: Portfolio overview with real-time updates
2. **Portfolio Management**: Position tracking and P&L analysis
3. **Risk Monitoring**: Real-time risk metrics and alerts
4. **Strategy Analysis**: Performance tracking and comparison
5. **System Health**: Operational monitoring dashboard

### Success Criteria
- **User Experience**: Trader can assess portfolio status within 5 seconds
- **Real-time Performance**: Updates reflect backend changes within 1 second
- **Mobile Usability**: Full functionality available on tablet/mobile
- **Reliability**: 99.9% uptime with graceful degradation
- **Performance**: Sub-2 second load times for all pages

### Risk Mitigation
- **Fallback UI**: Graceful handling of API failures
- **Data Validation**: Client-side validation of all financial data
- **Error Boundaries**: Prevent single component failures from crashing app
- **Monitoring**: Comprehensive error tracking and performance monitoring
- **Security**: Secure handling of authentication and sensitive financial data

This frontend should provide a professional, real-time trading interface that enables effective monitoring of the algorithmic trading system with minimal cognitive overhead for the user.