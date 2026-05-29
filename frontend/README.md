# Sports Prediction Frontend

React/Next.js 14 frontend for the Sports Prediction System.

## Prerequisites

- Node.js 18+ (LTS recommended)
- npm or yarn

## Setup

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Update API URL if needed (default: http://localhost:8004)
# Edit .env.local and set NEXT_PUBLIC_API_URL
```

## Development

```bash
# Start development server
npm run dev

# Server runs on http://localhost:3000
```

## Building

```bash
# Create production build
npm run build

# Start production server
npm start
```

## Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

## Linting

```bash
# Check code quality
npm run lint
```

## Project Structure

```
src/
├── app/              # Next.js App Router pages
│   ├── layout.tsx    # Root layout
│   ├── page.tsx      # Dashboard (/)
│   ├── matches/      # /matches route
│   ├── reports/      # /reports route
│   ├── market/       # /market route (WIP)
│   └── globals.css   # Global styles
├── components/       # React components
│   ├── PredictionCard
│   ├── BiometricGauge
│   ├── SHAPWaterfall
│   ├── LineMovementChart
│   ├── SentimentBadge
│   └── __tests__/    # Component tests
├── lib/              # Utilities
│   ├── api.ts        # API client
│   ├── ws.ts         # WebSocket hook
│   └── __tests__/    # Library tests
└── types/            # TypeScript interfaces
    └── index.ts
```

## Pages

### Dashboard (`/`)
Real-time overview with key metrics and upcoming matches.

### Matches (`/matches`)
Browsable list of matches with value bet identification. Filter by date, sort by edge or Kelly %.

### Match Detail (`/matches/[matchId]`)
Detailed prediction view with:
- Win/Draw/Loss probabilities
- SHAP feature importance waterfall
- Biometric readiness gauges
- Line movement tracking
- Sentiment analysis badges
- Live WebSocket updates

### Reports (`/reports`)
Generated match research reports with PDF export.

### Market (`/market`)
[In Development] Market analysis and odds comparison.

## API Integration

Connects to backend at `NEXT_PUBLIC_API_URL` (default: `http://localhost:8004`)

### Endpoints Used
- `GET /health` — Service health check
- `GET /api/v1/predictions/{match_id}` — Single match prediction
- `POST /api/v1/predictions/batch` — Batch predictions
- `GET /api/v1/value-bets` — Value bet recommendations
- `GET /api/v1/reports/{match_id}` — Match report data
- `GET /api/v1/reports/{match_id}/pdf` — PDF export
- `GET /models` — Model info
- `WS /ws/live/{match_id}` — Live prediction updates

## Environment Variables

| Variable | Default | Description |
|:---|:---|:---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8004` | Backend API base URL |
| `NEXT_PUBLIC_API_KEY` | `` | Optional API key sent as `X-API-Key` header |

## Stack

- **Framework:** Next.js 14
- **Language:** TypeScript 5.3
- **Styling:** Tailwind CSS 3.4
- **UI Components:** Lucide Icons 0.312
- **Charts:** Recharts 2.10
- **Testing:** Jest 29.7, React Testing Library 14.1
- **Linting:** ESLint 8.56

## Known Issues

- `/market` page not yet implemented
- LineMovementChart component needs full implementation
- SentimentBadge styling needs expansion

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests: `npm test`
4. Run linter: `npm run lint`
5. Build: `npm run build`
6. Submit PR

## License

Proprietary — Sports Prediction System
