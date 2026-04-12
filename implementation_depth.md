# FinTwin: Implementation Depth Matrix

This document breaks down the 10 architecture tiers into their exact sub-features, tracking their presence across the backend logic and the frontend user experience.

---

### 1. Multi-Source Signal Ingestion
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Bank Transactions** | Data generation pipeline inside `src/ingestion` mapping raw financial activity. | Visualized in the `Transactions` tab of the Digital Twin via `TimeSeriesPanel.tsx`. | ✅ Implemented |
| **UPI Logs** | Specialized UPI ledger parsing mock objects. | Loaded as `upi_timeline` state inside `TimeSeriesPanel.tsx`. | ✅ Implemented |
| **SMS Alerts** | Regex scraping blueprints designed in ingestion layers. | — | 🚧 Partial (Math mocked, UI pending real endpoint) |
| **EMI Schedules** | Loan structuring tracking arrays linking to risk metrics. | Integrated into the Tier 8 Negotiation interventions for restructuring. | ✅ Implemented |
| **Open-Banking Feeds** | API structural hooks for Account Aggregator protocols. | Displayed as general aggregated financial states across `msme/report/page.tsx`. | ✅ Implemented |

### 2. Event Stream Processor
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Real-time Event Classification** | Categorization mapped by `src/classifier/` (assigning types like 'cash_flow', 'default_risk'). | Real-time classification logs surface in the "Business Risk Alerts" notification cluster. | ✅ Implemented |
| **Sliding-Window Aggregation** | Mathematical sliding windows calculated natively in Python (`src/features/`). | Visualized actively as the 30/60/90 Day Default Trajectories inside the Scenario Simulator tab. | ✅ Implemented |

### 3. Behavioural Feature Engine
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Spending Volatility** | Variance algorithms tracking outflow spikes vs standard deviation. | Specific "Volatility Score" metric dials on the `msme/report/page.tsx` Score Report. | ✅ Implemented |
| **Income Stability** | Consistency mathematical benchmarking across historical months. | "Income Stability" grading on the full Credit Report view. | ✅ Implemented |
| **Peer Cohort Benchmarking** | Distribution curves evaluating user score arrays against local industry metrics. | General percentile positioning mapping. | 🚧 Partial (Need distinct UI graphs for market comparison) |
| **Trend Detection** | Time-series slope extraction scripts. | Rendered flawlessly via `Recharts` inside `dashboard/page.tsx` and the Twin Evolution Timeline. | ✅ Implemented |

### 4. Digital Twin State Layer
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Stateful, Versioned Twin** | `src/twin/` captures persistent, immutable iterations of a user's financial profile. | Twin Evolution History tab mapping individual `ver` states like v2, v3, etc. | ✅ Implemented |
| **DNA Fingerprint** | Mapping behavioural signals into literal named cohorts. | Exposed directly as the `persona` trait (e.g., "Steady Earner", "Volatile Vendor") in Twin header. | ✅ Implemented |
| **Temporal Replay** | Fetching historical array structures. | The Twin Timeline LineChart rebuilding prior historical states dynamically. | ✅ Implemented |

### 5. LLM Reasoning Layer
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Narrative Intelligence** | DeepSeek V3 system-prompt construction (`api/chat/route.ts`). | The interactive Chatbots across the Masterclass Guide UI. | ✅ Implemented |
| **Chain-of-Thought Reasoning** | `src/reasoning/` trace arrays extracting step-by-step logic from the LLM. | Rendered utilizing the `normalizeCotSteps()` parser into expandable T1, T2 dropdowns under the "AI Reasoning" tab. | ✅ Implemented |
| **Contradiction Detection** | LLM layer internal system flags designed to spot narrative logic crashes. | Tagged automatically as "Concern Flags" inside the Reasoning arrays. | ✅ Implemented |

### 6. Predictive Risk Simulation
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Monte Carlo Risk Projections** | Probabilistic fan chart generation returning p10, p50, and p90 traces. | Advanced stacked `AreaChart` rendering 60-day visual fan spread trajectories in the Simulator. | ✅ Implemented |
| **Stress Tests** | Overriding live variable states with severe negative constants. | Single-click buttons like "GST Shock", "Revenue Crash -40%" firing manual triggers to the twin engine. | ✅ Implemented |
| **Recovery Path Modelling** | Long-tail P10 scenario generations mapping slow financial bounce-backs. | Rendered within the Monte Carlo Area projection curves dynamically. | ✅ Implemented |

### 7. Cognitive Credit Engine
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Behaviour-Aware Dynamic Decisioning** | `src/scoring/` translating non-standard behavioural data into direct credit bandwidths. | The live `twinScore` / `derivedWc` allocations generated upon pressing "Submit Score Request". | ✅ Implemented |
| **Bureau Integration** | Algorithmic smoothing formula syncing FinTwin risk% with traditional bureau digits. | Displayed distinctly as the "CIBIL-like" representation mapping alongside the twin risk array. | ✅ Implemented |

### 8. Proactive Intervention Agent
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Autonomous Contextual Nudges** | Edge-runtime trigger evaluations. | Headless `/api/whatsapp-alert/route.ts` bridging the backend to Meta/WhatsApp messaging natively. | ✅ Implemented |
| **Micro-loan Push** | Push generation based on localized pre-approval limits. | Live "Pre-qualified offer generated" Toast/Feed pushes appearing conditionally on score improvements. | ✅ Implemented |
| **EMI Negotiation** | Conversational API states tracking structured prompt interactions. | Advanced Tier 8 Negotiation Console with "Generate Offer" -> "Discuss Restructure" chat looping. | ✅ Implemented |

### 9. Anomaly & Deception Detection
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Fraud Signals** | High severity trigger evaluation engine (`src/vigilance/`). | Distinctly stylized Red/Orange warnings listed in the Twin's "Risk Alerts" module. | ✅ Implemented |
| **Scam Defence** | Pattern recognition tracking inbound transactional spikes against norms. | Full `vigilance/page.tsx` threat command center dashboard mapping external risks. | ✅ Implemented |
| **Synthetic Identity Scoring** | Profile verification heuristics on identity layer signals. | Represented internally across the Vigilance hub. | ✅ Implemented |

### 10. Audit Repository & Dashboard
| Subfeature | Backend Implementation | Frontend Representation | Status |
| :--- | :--- | :--- | :--- |
| **Full-Stack Live Dashboard** | Aggressive API aggregations across twin core functions. | `dashboard/page.tsx` mapping aggregate UI metrics. | ✅ Implemented |
| **What-if Simulation** | Parameter overrides enabling manual what-if injections. | The adjustable "Income / Revenue Change" sliders inside the Simulator tab. | ✅ Implemented |
| **Regulatory Audit Export** | Local JSON payload compilers and HTML builder functions. | The instantaneous click-to-download `exportPdf()` and `exportJson()` actions on the Twin Page header logic. | ✅ Implemented |
