# Frontend Design — Log Analysis & Incident Response Agent
# React + TypeScript UI Specification

---

## 1. Vision & Aesthetic Direction

**Subject:** Real-time AI-powered incident investigation interface for SRE engineers.  
**Audience:** On-call engineers, incident commanders — people who trust terminals, distrust dashboards, and need answers in seconds, not minutes.  
**Single job:** Let an engineer ask natural language questions about a live incident and instantly see the agent's reasoning, tool calls, and conclusions — without ever touching a CLI.

**Tone:** Ops room, not consumer app. The aesthetic is a military operations center in daylight — clinical white surfaces with surgical precision, where red alerts hit harder than on any dark background. This is deliberate. War rooms use whiteboards. Radar operators work in lit rooms. The data is the violence; the UI should stay out of the way.

**The Aesthetic Risk — Horizontal Service Timeline:**  
Instead of the default vertical log feed, the primary data canvas is a horizontal time-flow grid. Services run top-to-bottom as rows; time runs left-to-right. Each log event is a positioned glyph at its exact timestamp. The 5-minute incident window (15:20–15:25) becomes a spatial story you can read at a glance — you see `db-service` fail, watch `checkout-service` react 18 seconds later, and then see `api-gateway` open the circuit breaker. No scrolling required for temporal correlation. This is the risk; it pays off for incident investigators because time and causation are the only things that matter.

---

## 2. Design Tokens

### 2.1 Color System

```css
:root {
  /* Ground & Surfaces */
  --ground:          #F7F8FA;   /* Near-white with a touch of cool blue */
  --surface:         #FFFFFF;   /* Cards, panels */
  --surface-raised:  #EFF1F5;   /* Hover states, subtle containers */
  --surface-inverse: #0D1117;   /* Code blocks, terminal segments */

  /* Typography */
  --text-primary:    #0D1117;   /* Near-black — all body copy */
  --text-secondary:  #4B5563;   /* Labels, metadata */
  --text-muted:      #9CA3AF;   /* Placeholders, disabled */
  --text-inverse:    #E6EDF3;   /* Text on dark surfaces */

  /* Borders */
  --border-default:  #E2E5EA;
  --border-strong:   #C9CDD5;

  /* Accent — Signal Amber */
  --amber:           #E07B39;   /* Primary accent: warning, active, agent */
  --amber-dim:       #E07B3918; /* 9% opacity for tinted backgrounds */
  --amber-mid:       #E07B3940; /* 25% opacity for focus rings */

  /* Semantic Status */
  --critical:        #DC2626;   /* ERROR / CRITICAL logs */
  --critical-dim:    #DC262612;
  --warn:            #CA8A04;   /* WARN logs */
  --warn-dim:        #CA8A0412;
  --success:         #16A34A;   /* PASSED verification, INFO logs */
  --success-dim:     #16A34A12;
  --info:            #2563EB;   /* Info states, links */
  --info-dim:        #2563EB12;
  --runbook:         #7C3AED;   /* RUNBOOK level logs */
  --runbook-dim:     #7C3AED12;

  /* Agent Step Colors */
  --step-observe:    #2563EB;
  --step-reason:     #7C3AED;
  --step-plan:       #E07B39;
  --step-act:        #CA8A04;
  --step-verify:     #16A34A;
  --step-complete:   #16A34A;
  --step-failed:     #DC2626;
  --step-iterate:    #E07B39;

  /* Shadows */
  --shadow-card:     0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-raised:   0 4px 12px rgba(0,0,0,0.10), 0 2px 4px rgba(0,0,0,0.06);
  --shadow-overlay:  0 20px 60px rgba(0,0,0,0.15), 0 8px 20px rgba(0,0,0,0.08);
}
```

**Palette rationale:**  
Light ground breaks from every dark SRE dashboard on the market. The amber accent (`#E07B39`) is the signal color: caution, active investigation, the "we're not done yet" state. It's the amber light on a server rack, the yellow stripe on hazard tape — not solved, not broken, still watching. When CRITICAL logs hit, red against white is viscerally alarming in a way red against dark gray never is.

### 2.2 Typography

```css
/* Import (add to index.html <head>) */
/* Google Fonts: Syne (Display) + Figtree (UI) + Geist Mono (Code) */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Figtree:wght@300;400;500;600&family=Geist+Mono:wght@300;400;500&display=swap');

:root {
  --font-display: 'Syne', sans-serif;       /* Brand name, section titles */
  --font-body:    'Figtree', sans-serif;     /* All UI text */
  --font-mono:    'Geist Mono', monospace;   /* Log data, code, timestamps */

  /* Type Scale */
  --text-xs:    11px;
  --text-sm:    13px;
  --text-base:  15px;
  --text-lg:    17px;
  --text-xl:    20px;
  --text-2xl:   26px;
  --text-3xl:   34px;
  --text-4xl:   48px;

  /* Line Heights */
  --leading-tight:  1.2;
  --leading-snug:   1.35;
  --leading-normal: 1.55;
  --leading-loose:  1.75;

  /* Letter Spacing */
  --tracking-tight:  -0.02em;
  --tracking-normal: 0;
  --tracking-wide:   0.04em;
  --tracking-wider:  0.08em;
  --tracking-widest: 0.16em;
}
```

**Typography logic:**
- **Syne** (display): Geometric with quirky open apertures — used only for the app name, page titles, and anomaly scores. Its character shows at large sizes. Never body text.
- **Figtree**: Friendly rounded geometric sans. Very readable at 13–15px, which is where log metadata lives. Not Inter. Not Roboto.
- **Geist Mono**: Vercel's monospace, purpose-built for code and data. Every timestamp, log_id, error_code, and JSON payload uses this. The mono font is a first-class typographic voice here.

### 2.3 Spacing & Radius

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-xl:  16px;
  --radius-full: 9999px;
}
```

---

## 3. Application Architecture

### 3.1 Route Structure

```
/                    → Redirects to /incident/demo
/incident/:sessionId → Main investigation interface (primary view)
/history             → Past investigation sessions list
/settings            → API key, model config
```

### 3.2 Layout Model

The app is a two-pane workspace. Left pane is fixed-width (400px). Right pane takes all remaining space and contains the dynamic context workspace.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TOPBAR: amber logo + session ID + agent step indicator + status        │
├────────────────────┬────────────────────────────────────────────────────┤
│                    │                                                    │
│   CHAT PANEL       │         CONTEXT WORKSPACE                          │
│   (400px fixed)    │         (fluid)                                    │
│                    │                                                    │
│  ┌──────────────┐  │   [Timeline] or [Anomaly] or [Runbook] or          │
│  │ Conversation │  │   [Report] — switches based on last tool used      │
│  │ history      │  │                                                    │
│  │              │  │                                                    │
│  │              │  │                                                    │
│  │              │  │                                                    │
│  └──────────────┘  │                                                    │
│  ┌──────────────┐  │                                                    │
│  │ Input + send │  │                                                    │
│  └──────────────┘  │                                                    │
│  ┌──────────────┐  │                                                    │
│  │ Demo run btn │  │                                                    │
│  └──────────────┘  │                                                    │
└────────────────────┴────────────────────────────────────────────────────┘
```

### 3.3 Context Workspace Tabs

```
[Timeline] [Anomaly] [Tools] [Runbook] [Report]
```

Tab becomes active + amber-underlined when its domain data is available. The workspace auto-switches to the relevant tab when the agent produces new data for it.

---

## 4. Component Specifications

### 4.1 Topbar

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ◈ SENTRY         INC-2024-0115   ●──●──●──●──●──○    VERIFY  ▣ 45s   │
│  (amber logo)     (session id)    (step pipeline)     (current) (timer) │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component: `Topbar.tsx`**

Props:
```typescript
interface TopbarProps {
  sessionId: string;
  currentStep: AgentStep;
  stepsExecuted: AgentStep[];
  elapsedSeconds: number;
  verificationStatus: VerificationStatus;
}
```

- Logo: "◈ SENTRY" in Syne 600, amber color. "SENTRY" is the UI's name for the agent.
- Session ID: Geist Mono, text-muted. Clickable → copies to clipboard.
- Step pipeline: 6 dots representing OBSERVE→REASON→PLAN→ACT→VERIFY→COMPLETE. Completed steps filled amber. Current step pulses. Failed = red.
- Current step: All-caps label in Figtree 500, tracking-widest, colored by step.
- Timer: Geist Mono, text-secondary. Counts up while active.

### 4.2 Chat Panel

```
┌────────────────────────────────┐
│  INVESTIGATION                 │ ← Syne 600, 13px, tracking-widest
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ USER                     │  │ ← Figtree 500 12px amber
│  │ Analyze logs from        │  │
│  │ 15:20-15:25 and detect   │  │
│  │ any anomalies            │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ ◈ AGENT  · 2.3s          │  │ ← amber dot + timing
│  │                          │  │
│  │ [● LogRetrieverTool]     │  │ ← tool call chip (amber bg-dim)
│  │ [● AnomalyAnalysisTool]  │  │
│  │                          │  │
│  │ Detected a HIGH-risk     │  │ ← response text, Figtree 400 14px
│  │ anomaly at 15:22. Score  │  │
│  │ 87/100. DB connection    │  │
│  │ pool exhausted...        │  │
│  └──────────────────────────┘  │
│                                │
│  [thinking...]                 │ ← animated skeleton when streaming
│                                │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  Ask about this incident │  │ ← placeholder text
│  │                          │  │
│  └──────────┬───────────────┘  │
│             │ ↵ SEND           │
└─────────────┴──────────────────┘
```

**Component: `ChatPanel.tsx`**

```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  toolsUsed?: string[];
  elapsedMs?: number;
  timestamp: Date;
  streaming?: boolean;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (message: string) => void;
  onRunDemo: () => void;
  isLoading: boolean;
}
```

Message bubbles:
- **User**: Right-aligned? No — left-aligned, amber `USER` eyebrow, slight amber-dim background. No chat-bubble rounding (not a consumer messenger).
- **Agent**: Left-aligned, `◈ AGENT` eyebrow in amber, white surface, border-left: 3px solid amber. Elapsed time in Geist Mono next to eyebrow.
- **Tool chips**: Inside agent messages. `● LogRetrieverTool` — filled circle + tool name in Geist Mono 12px, amber-dim background, amber text.
- **Streaming state**: Three dots animation, text renders character by character via SSE.

**Demo Button:**
```
┌──────────────────────────────┐
│  ▶  Run Demo Scenario        │
│     5 questions · auto mode  │
└──────────────────────────────┘
```
Full-width, amber background, white text. Disabled when session is active.

### 4.3 Service Timeline (Primary Context View)

**This is the aesthetic risk.** A horizontal multitrack timeline where every log event is positioned at its exact timestamp.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SERVICE TIMELINE  15:20:00 → 15:25:00          ● 25 events    [ZOOM]  │
├───────────────┬─────────────────────────────────────────────────────────┤
│               │ 15:20      15:21      15:22      15:23      15:24      │
│               ├────────────────────────────────────────────────────────│
│  api-gateway  │ ○              ○           ▲ ▲          ◆              │
│               │                                                         │
│  checkout-svc │     ○    ○        △    ▲ ▲ ▲    ◆                      │
│               │                                                         │
│  db-service   │          △    △  ▲▲ ▲▲▲ ▲▲ ▲   ◆◆ ◆                  │
│               │                                                         │
│  cache-service│                      △         ◆                       │
│               │                                                         │
│  auth-service │ ○ ○ ○ ○                                                │
├───────────────┴─────────────────────────────────────────────────────────┤
│  LEGEND: ○ INFO  △ WARN  ▲ ERROR  ◆ CRITICAL  ■ RUNBOOK               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component: `ServiceTimeline.tsx`**

```typescript
interface TimelineEvent {
  log_id: string;
  timestamp: string;
  service: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL' | 'RUNBOOK';
  error_code: number | string;
  message: string;
  request_id: string;
  duration_ms: number;
}

interface ServiceTimelineProps {
  events: TimelineEvent[];
  timeStart: string;  // "15:20"
  timeEnd: string;    // "15:25"
  onEventClick: (event: TimelineEvent) => void;
  highlightRequestId?: string;
}
```

Implementation notes:
- Built with SVG or canvas (not DOM elements for performance at scale)
- Services are rows (fixed 48px height each)
- Time axis is continuous (minutes marked with thin gray rules)
- Events are clickable glyphs — hover shows tooltip with full log line
- Click highlights the request_id chain across all services (amber outline on all events sharing the request_id)
- Zoom: scroll wheel scales the time axis; pan with click-drag
- The "cascade failure" at 15:22 becomes visually obvious: db-service events cluster, then checkout errors appear milliseconds later
- Event glyph size encodes `duration_ms` (larger = longer operation)

**Event Detail Tooltip:**
```
┌─────────────────────────────────────────────┐
│  LOG013 · db-service · 15:22:08             │
│  ─────────────────────────────────────────  │
│  DB connection pool exhausted (100/100)     │
│  47 queries waiting                         │
│                                             │
│  error_code  500    duration  0ms           │
│  request_id  REQ009                         │
│  host        db-node-01                     │
│                                             │
│  [Highlight chain →]                        │
└─────────────────────────────────────────────┘
```

### 4.4 Anomaly Dashboard (Context tab: Anomaly)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANOMALY ANALYSIS · 15:20–15:25                         HIGH RISK  ◈   │
├────────────────────────┬────────────────────────────────────────────────┤
│                        │                                                │
│         87             │  CORRELATION CHAIN                             │
│      ANOMALY           │                                                │
│       SCORE            │  db-service → checkout-service → api-gateway  │
│                        │      ◆ pool    →  ▲ timeout  →  ▲ 503        │
│  ████████████████░░░░  │                                                │
│  (amber progress bar)  │  REPEATING PATTERNS                            │
│                        │  ─────────────────────────────────────────    │
│  Peak rate   8.4 err/m │  ● DB connection pool exhausted      4×       │
│  Baseline    1.2 err/m │  ● connection timeout                3×       │
│  Spike at    15:22:08  │  ● slow query detected               2×       │
│                        │                                                │
│  Recurrence  ~12 min   │  HISTORICAL MATCHES                            │
│  Escalated   YES ◆     │  ─────────────────────────────────────────    │
│                        │  INC001 · 2023-11-02 · 25min resolution       │
│                        │  INC004 · 2023-09-14 · 18min resolution       │
└────────────────────────┴────────────────────────────────────────────────┘
```

**Component: `AnomalyDashboard.tsx`**

```typescript
interface AnomalyData {
  anomaly_score: number;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  error_rate_baseline: number;
  error_rate_peak: number;
  spike_detected_at: string;
  repeating_patterns: string[];
  pattern_interval_seconds: number;
  affected_services: string[];
  root_cause_service: string;
  root_cause: string;
  root_cause_type: string;
  correlation_chain: string;
  recurrence_prediction_minutes: number;
  escalated: boolean;
  reasons: string[];
  matched_past_incidents: HistoricalIncident[];
  historical_match_count: number;
}

interface AnomalyDashboardProps {
  data: AnomalyData;
}
```

Score display:
- Large number (48px Syne 800) — "87" with "/100" in 20px text-muted below
- Color: text-primary if ≤50, warn if ≤80, critical if >80
- Below: amber animated progress bar (width = anomaly_score%)

Correlation chain: Visual flow diagram with service boxes connected by arrows. Each box colored by severity of events from that service. Arrow direction = causation direction.

### 4.5 Tool Execution Panel (Context tab: Tools)

Shows all 6 tool calls in order of execution during the session.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TOOL EXECUTIONS · Session INC-20240115-1522                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✓ LogRetrieverTool          RETRIEVAL           0.12s    L1 PASS       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ query: "15:20-15:25"  →  25 logs retrieved                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ✓ LogNormalizeTool           PROCESSING          0.08s    L1 PASS      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ 25 logs → enriched with error_category, time_bucket, is_error   │    │
│  │ top_pattern: "DB connection pool exhausted" (4×)                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ✓ AnomalyAnalysisTool        ANALYSIS            0.34s    L1 PASS      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ score: 87  risk: HIGH  spike: 15:22:08  escalated: true          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ✓ LogOutputVerifierTool      VERIFICATION        0.05s    L1 PASS      │
│  ✓ RunbookGeneratorTool       EXECUTION           0.21s    L1 PASS      │
│  ✓ IncidentReportTool         REPORTING           0.18s    L1 PASS      │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  LAYER 3 VERIFICATION                                                   │
│  All 6 required tools executed  ✓ PASSED                                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component: `ToolExecutionPanel.tsx`**

```typescript
interface ToolExecution {
  toolName: string;
  category: 'Retrieval' | 'Processing' | 'Execution' | 'Verification' | 'Analysis' | 'Reporting';
  elapsedMs: number;
  layer1Passed: boolean;
  inputSummary: string;
  outputSummary: string;
  status: 'pending' | 'running' | 'success' | 'error';
}

interface ToolExecutionPanelProps {
  executions: ToolExecution[];
  layer3Status: { passed: boolean; failures: string[] };
}
```

Category badge colors:
```
Retrieval    → info (#2563EB) background dim
Processing   → runbook (#7C3AED) background dim
Execution    → amber (#E07B39) background dim
Verification → warn (#CA8A04) background dim
Analysis     → critical (#DC2626) background dim
Reporting    → success (#16A34A) background dim
```

L1 PASS badge: 10px Geist Mono, success-colored, right-aligned in tool row header.

Running animation: Shimmer on the tool row while executing (CSS animation, not JS).

### 4.6 Runbook Viewer (Context tab: Runbook)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  RUNBOOK · RB001                                    INC-20240115-1522   │
│  DB connection pool exhausted                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AFFECTED SERVICES                                                      │
│  ┌────────────────┐ ┌────────────────┐ ┌───────────────┐               │
│  │  api-gateway   │ │checkout-service│ │  db-service   │               │
│  └────────────────┘ └────────────────┘ └───────────────┘               │
│                                                                         │
│  REMEDIATION STEPS                                                      │
│  ──────────────────────────────────────────────────────────────────    │
│  □  1  Kill slow query: KILL QUERY 4821;                                │
│  □  2  Increase DB connection pool:                                     │
│        SET global max_connections=200;                                  │
│  □  3  Restart checkout-service to flush stale handles                  │
│  □  4  Add circuit breaker between checkout-service and db-service      │
│  □  5  Monitor: watch -n5 'ss -s | grep ESTAB'                         │
│                                                                         │
│  ──────────────────────────────────────────────────────────────────    │
│  ETA ~5 min    ESCALATION  db-team@company.com    [Copy runbook →]      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component: `RunbookViewer.tsx`**

```typescript
interface RunbookData {
  runbook_id: string;
  incident_id: string;
  root_cause: string;
  affected_services: string[];
  fix_steps: string[];
  rollback_steps: string[];
  estimated_resolution_minutes: number;
  escalation_contact: string;
}

interface RunbookViewerProps {
  data: RunbookData;
}
```

Fix steps are interactive: clicking a checkbox marks it done (local state only, for during-incident tracking). Step text containing backtick-wrapped commands renders in Geist Mono with amber text.

### 4.7 Incident Report (Context tab: Report)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INCIDENT REPORT · 15:20–15:25             Generated  2024-01-15 15:26  │
├──────────────────────────────────────────────────────────────────────── │
│                                                                         │
│  SUMMARY                                                                │
│  DB connection pool exhausted on db-service causing cascading           │
│  timeouts across checkout-service and api-gateway. 47 queued           │
│  requests blocked for 2+ minutes. Circuit breaker activated 15:24.     │
│                                                                         │
│  METRICS                                                                │
│  Total logs    25     Error count   14    Critical count   4            │
│  Top service   db-service (8 errors)                                    │
│                                                                         │
│  SERVICES INVOLVED                                                      │
│  api-gateway  checkout-service  db-service  cache-service  auth-service │
│                                                                         │
│  POST-MORTEM ACTIONS                                                    │
│  ● Increase DB connection pool size to 200                              │
│  ● Kill long-running query #4821                                        │
│  ● Add circuit breaker to checkout-service → db-service path           │
│  ● Set up alerting at error_rate > 10/min                               │
│  ● Review slow query log and add missing index                          │
│                                                                         │
│  HISTORICAL CONTEXT                                                     │
│  Similar incident INC001 resolved in 25 min (2023-11-02)                │
│  Recurs every ~14 days. Use runbook RB001.                              │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  LAYER 3 VERIFICATION                          ✓ ALL 6 TOOLS EXECUTED  │
│  LogRetrieverTool  LogNormalizeTool  RunbookGeneratorTool  ✓✓✓          │
│  LogOutputVerifierTool  AnomalyAnalysisTool  IncidentReportTool  ✓✓✓   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component: `IncidentReport.tsx`**

```typescript
interface ReportData {
  summary: IncidentSummary;
  layer3_verification: Layer3Verification;
}

interface IncidentSummary {
  time_range: string;
  total_logs: number;
  error_count: number;
  critical_count: number;
  services: string[];
  top_error_service: string;
  incident_summary: string;
  historical_context: HistoricalContext;
  post_mortem_actions: string[];
}

interface Layer3Verification {
  passed: boolean;
  failures: string[];
  tools_found: string[];
}

interface IncidentReportProps {
  data: ReportData;
  generatedAt: Date;
}
```

Layer 3 badge at bottom: Large pill, full-width.
- If passed: success-dim background, "✓ ALL 6 TOOLS EXECUTED · LAYER 3 PASSED"
- If failed: critical-dim background, lists missing tools

Export button: "Export JSON" copies `output/report.json` content to clipboard.

### 4.8 Agent Step Indicator (inside Topbar)

```typescript
// AgentStep enum values from state.py
type AgentStep = 'IDLE' | 'OBSERVE' | 'REASON' | 'PLAN' | 'ACT' | 'VERIFY' | 'ITERATE' | 'COMPLETE' | 'FAILED';

type VerificationStatus = 'PENDING' | 'PASSED' | 'FAILED' | 'PARTIAL';
```

The pipeline shows 6 canonical steps: OBSERVE → REASON → PLAN → ACT → VERIFY → COMPLETE.

Each is a 10px circle. Completed = filled amber. Current = pulsing amber ring. Pending = empty gray ring. FAILED anywhere = that circle turns red, subsequent circles gray. ITERATE = ACT circle gains a ↻ icon.

### 4.9 Verification Status Badge

Used in multiple places. Single component.

```typescript
interface VerificationBadgeProps {
  status: VerificationStatus;
  layer: 1 | 2 | 3;
  failures?: string[];
}
```

Renders:
- `PASSED` → green background, "L{n} PASS" text
- `FAILED` → red background, "L{n} FAIL" text, expandable failures list
- `PARTIAL` → amber background, "L{n} PARTIAL" text
- `PENDING` → gray background, "L{n} ..." with spinner

---

## 5. State Management

### 5.1 Zustand Store

```typescript
// src/store/agentStore.ts
import { create } from 'zustand';

interface AgentSession {
  sessionId: string;
  currentStep: AgentStep;
  stepsExecuted: AgentStep[];
  toolsUsed: string[];
  verificationStatus: VerificationStatus;
  retries: number;
  elapsedSeconds: number;
  errors: string[];
  messages: ChatMessage[];
  anomalyData: AnomalyData | null;
  runbookData: RunbookData | null;
  reportData: ReportData | null;
  timelineEvents: TimelineEvent[];
  toolExecutions: ToolExecution[];
  activeTab: 'timeline' | 'anomaly' | 'tools' | 'runbook' | 'report';
  isStreaming: boolean;
}

interface AgentStore extends AgentSession {
  // Actions
  startSession: () => void;
  sendMessage: (message: string) => void;
  runDemo: () => void;
  setActiveTab: (tab: AgentSession['activeTab']) => void;
  updateFromSSE: (event: SSEEvent) => void;
  reset: () => void;
}
```

### 5.2 SSE Event Types

```typescript
// Events streamed from Python FastAPI backend
type SSEEvent =
  | { type: 'step_change'; step: AgentStep }
  | { type: 'tool_start'; toolName: string; category: string; input: string }
  | { type: 'tool_end'; toolName: string; result: ToolResult; elapsedMs: number }
  | { type: 'agent_token'; token: string }  // For streaming LLM output
  | { type: 'agent_done'; fullResponse: string; verificationStatus: VerificationStatus }
  | { type: 'timeline_data'; events: TimelineEvent[] }
  | { type: 'anomaly_data'; data: AnomalyData }
  | { type: 'runbook_data'; data: RunbookData }
  | { type: 'report_data'; data: ReportData }
  | { type: 'session_complete'; output: AgentOutput }
  | { type: 'error'; message: string };
```

---

## 6. API Integration Layer

The Python backend needs a thin FastAPI wrapper to expose the agent as HTTP endpoints. The UI communicates via SSE for streaming and REST for simple queries.

### 6.1 Required Backend Endpoints

```
POST /api/sessions                 → Create new session, returns { sessionId }
POST /api/sessions/:id/chat        → Send message, SSE stream response
POST /api/sessions/:id/demo        → Trigger demo run, SSE stream events
GET  /api/sessions/:id/logs        → Return raw logs.csv data as JSON
GET  /api/sessions/:id/output      → Return saved report.json
GET  /api/sessions                 → List past sessions
```

### 6.2 FastAPI Wrapper (add to project as `src/api.py`)

```python
# Key structure — implement with:
# uvicorn src.api:app --reload --port 8000

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)

@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest):
    async def event_stream():
        # Hook into agent.chat() with a custom callback that yields SSE events
        # Each tool call, step change, and LLM token → yield "data: {json}\n\n"
        pass
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### 6.3 React API Client

```typescript
// src/api/client.ts
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function sendMessage(sessionId: string, message: string, onEvent: (e: SSEEvent) => void) {
  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}
```

---

## 7. Animation Specifications

**Philosophy:** One orchestrated moment of motion matters more than scattered micro-interactions. The single animated moment is the **incident timeline appearance** — events populate left-to-right on mount, clustering at 15:22 like a dam bursting. Everything else is either instant or subtly transitional.

```css
/* Global transition defaults */
* { transition-duration: 150ms; transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1); }

/* Agent step pulse — only the active step */
@keyframes stepPulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--amber-mid); }
  50%       { box-shadow: 0 0 0 6px transparent; }
}

/* Timeline event entrance — staggered by timestamp offset */
@keyframes eventPop {
  from { opacity: 0; transform: scale(0.3); }
  to   { opacity: 1; transform: scale(1); }
}
.timeline-event {
  animation: eventPop 200ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  animation-delay: calc(var(--time-offset) * 1ms); /* CSS variable per event */
}

/* Tool execution shimmer */
@keyframes shimmer {
  from { background-position: -200% 0; }
  to   { background-position: 200% 0; }
}
.tool-running {
  background: linear-gradient(90deg, var(--surface-raised) 25%, var(--surface) 50%, var(--surface-raised) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* Streaming text cursor */
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
.streaming-cursor::after {
  content: '▋';
  color: var(--amber);
  animation: blink 600ms step-start infinite;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, .timeline-event { animation: none !important; transition: none !important; }
}
```

---

## 8. File Structure

```
agent-loganalysis-ui/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── .env.example          ← VITE_API_URL=http://localhost:8000
│
├── src/
│   ├── main.tsx
│   ├── App.tsx           ← Router + global providers
│   ├── index.css         ← CSS custom properties (tokens)
│   │
│   ├── store/
│   │   └── agentStore.ts
│   │
│   ├── api/
│   │   ├── client.ts
│   │   └── types.ts      ← All TypeScript interfaces
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Topbar.tsx
│   │   │   └── WorkspaceTabs.tsx
│   │   │
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ToolChip.tsx
│   │   │   └── ChatInput.tsx
│   │   │
│   │   ├── timeline/
│   │   │   ├── ServiceTimeline.tsx
│   │   │   ├── TimelineEvent.tsx
│   │   │   └── EventTooltip.tsx
│   │   │
│   │   ├── anomaly/
│   │   │   ├── AnomalyDashboard.tsx
│   │   │   ├── AnomalyScore.tsx
│   │   │   └── CorrelationChain.tsx
│   │   │
│   │   ├── tools/
│   │   │   ├── ToolExecutionPanel.tsx
│   │   │   └── ToolRow.tsx
│   │   │
│   │   ├── runbook/
│   │   │   └── RunbookViewer.tsx
│   │   │
│   │   ├── report/
│   │   │   └── IncidentReport.tsx
│   │   │
│   │   └── shared/
│   │       ├── VerificationBadge.tsx
│   │       ├── AgentStepPipeline.tsx
│   │       ├── ServiceBadge.tsx
│   │       └── StatusPill.tsx
│   │
│   ├── hooks/
│   │   ├── useAgentSession.ts    ← SSE connection + store updates
│   │   ├── useTimeline.ts        ← Timeline zoom/pan state
│   │   └── useElapsedTimer.ts
│   │
│   └── pages/
│       ├── InvestigationPage.tsx  ← Main two-pane layout
│       ├── HistoryPage.tsx
│       └── SettingsPage.tsx
│
└── public/
    └── favicon.svg               ← ◈ icon in amber
```

---

## 9. Package Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0",
    "zustand": "^4.5.4",
    "@tanstack/react-query": "^5.51.0",
    "date-fns": "^3.6.0",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.3.4"
  }
}
```

No UI component libraries (no shadcn, no MUI, no Radix). All components hand-built from the token system. The entire character of this UI comes from its own design system, not borrowed defaults.

---

## 10. Key Design Decisions Summary

| Decision | Choice | Reason |
|---|---|---|
| Background | Light (`#F7F8FA`) | Red critical alerts hit harder on white; war room whiteboard aesthetic |
| Primary accent | Signal Amber (`#E07B39`) | Investigation state: not solved (green), not broken (red) — watching |
| Display font | Syne | Geometric quirk at large sizes; unavoidable distinctiveness |
| Body font | Figtree | Friendly precision at 13–15px where log metadata lives |
| Mono font | Geist Mono | Purpose-built for data; first-class typographic voice |
| Main visualization | Horizontal timeline | Temporal correlation visible at a glance without scrolling |
| No component library | Hand-built | Token system IS the design; borrowed defaults erase it |
| No dark mode | Light only | Single deliberate choice, fully committed |
| Animation | Timeline entrance only | One orchestrated moment > scattered micro-interactions |
