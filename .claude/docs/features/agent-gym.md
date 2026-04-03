# Agent Gym — Self-Play Skill Training

MuZero/AlphaZero-inspired self-play engine where agents improve skills through practice, not just instruction.

## Training Loop

```
1. PLAY      → Agent attempts an exercise from its runner's skill set
2. EXECUTE   → Real code execution: compile, test, simulate (experimental verification)
3. GRADE     → 3-tier grading: experimental 40% + LLM critic 30% + structural 30%
4. CRITIQUE  → N critics (Gemini, Claude, Ollama, Human Expert, ...) review EXPERIMENTAL RESULTS
5. REFLECT   → Agent reviews its output vs critic feedback, generates improvement plan
6. REFINE    → Critics evolve acceptance criteria based on experimental evidence
7. COMPOUND  → Learnings stored in vector memory for next attempt
```

## Glicko-2 Skill Ratings

Each agent role × skill combination has a Glicko-2 rating:
- **Rating** (starts at 1000): skill level, clamped [100, 3000]
- **Rating Deviation (RD)**: confidence interval — starts high (350, uncertain), shrinks with data (min 30)
- **Volatility**: performance consistency — erratic agents have high volatility
- **Confidence interval**: rating ± 2×RD (95% confidence)
- **Streak tracking**: momentum detection for hot/cold streaks

## Exercise Catalog System

Scalable exercise system with ~661 industry-grade seed exercises across 11 domains:

| Domain | Seeds | Variant Axes | Potential Exercises |
|---|---|---|---|
| openfw | 60 | Platform, Architecture, RTOS, Safety | 6,000+ |
| openswe | 75 | Language, Framework, Scale, Pattern | 7,500+ |
| openml | 64 | Model, Dataset, Metric, Hardware | 6,400+ |
| openeda | 55 | Tool, Standard, Complexity, Freq | 5,500+ |
| opensim | 50 | Domain, Fidelity, Tool, Analysis | 5,000+ |
| opendoc | 58 | Standard, Domain, Audience, Format | 5,800+ |
| opendesign | 45 | Platform, Accessibility, Tool, Style | 4,500+ |
| openbrowser | 60 | Browser, Test Type, Framework, A11y | 6,000+ |
| openstrategy | 40 | Market, Methodology, Metric, Horizon | 4,000+ |
| openterminal | 68 | OS, Tool, Complexity, Domain | 6,800+ |
| autoresearch | 64 | Method, Domain, Metric, Scale | 6,400+ |

**Total**: ~50,000+ potential exercises via LLM-generated variants

## Spaced Repetition System

Failed exercises are scheduled for retry using spaced repetition:
- **Immediate retry**: Next training session
- **Short interval**: +1 session
- **Medium interval**: +3 sessions  
- **Long interval**: +7 sessions
- **Extended interval**: +15 sessions
- **Maximum interval**: +30 sessions

Exercises are cleared from spaced repetition when finally passed.

## Adaptive Exercise Selection

Three-tier selection algorithm optimizes learning:

1. **Tier 1 - Spaced Repetition** (highest priority)
   - Failed exercises due for retry
   - Ensures weak areas get attention
   
2. **Tier 2 - Optimal Challenge Zone** (medium priority)  
   - Exercises where success rate is 40-70%
   - Maximizes learning according to flow theory
   
3. **Tier 3 - Exploration** (lowest priority)
   - Unseen exercises for discovery
   - Prevents overfitting to known patterns

## Experimental Verification

Unlike traditional LLM training, the gym uses real toolchain execution:

### Domain-Specific Commands

Each runner provides experimental commands for verification:

- **OpenFW**: `arm-none-eabi-gcc`, `make`, `openocd flash`
- **OpenSWE**: `pytest`, `eslint`, `docker build` 
- **OpenML**: `python train.py`, `evaluate.py`, `tensorboard`
- **OpenEDA**: `kicad-cli`, `drc`, `gerber-export`
- **OpenSim**: `ngspice`, `iverilog`, `gtkwave`

### Grading Formula

**Final Score = (0.4 × Experimental) + (0.3 × LLM Critic) + (0.3 × Structural)**

- **Experimental (40%)**: Did it compile/run/pass tests?
- **LLM Critic (30%)**: Multi-provider code quality review
- **Structural (30%)**: Syntax, style, completeness checks

## Multi-Critic Review System

Agents receive feedback from multiple critics:

### LLM Critics
- **Primary**: Current LLM provider (weighted 1.5x)
- **Gemini**: Auto-discovered if available (weighted 1.0x)
- **Pool Providers**: Ollama, Mistral, etc. (weighted 1.0x)

### Human Expert Critic  
- **Weight**: 2.0x (highest reliability)
- **Process**: Queue → Expert Review → Submit Feedback
- **Integration**: Seamlessly merged with LLM critics

### Critic Prompt Customization

All critic prompts are editable by founders:
- `PLAN_REVIEW_PROMPT`
- `CODE_REVIEW_PROMPT` 
- `INTEGRATION_REVIEW_PROMPT`
- Custom domain-specific prompts

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/gym/train` | Start individual training session |
| `POST` | `/gym/train/batch` | Train multiple agents in parallel |
| `GET` | `/gym/session/{id}` | Get training session details |
| `GET` | `/gym/ratings` | Agent leaderboard (all roles) |
| `GET` | `/gym/ratings/{role}` | Ratings for specific role |
| `GET` | `/gym/history` | Recent training sessions |
| `GET` | `/gym/analytics` | Comprehensive analytics dashboard |
| `GET` | `/gym/curriculum/{role}` | Learning progression for role |
| `GET` | `/gym/catalog` | Exercise catalog statistics |
| `POST` | `/gym/catalog/generate` | Generate exercise variants |

## Analytics and Insights

### Performance Metrics
- **Success Rate Trends**: Track improvement over time
- **Skill Progression**: Rating evolution by domain
- **Weakness Analysis**: Identify persistent failure patterns
- **Learning Velocity**: Rate of improvement measurement

### Training Optimization
- **Difficulty Calibration**: Auto-adjust based on success rates
- **Exercise Diversity**: Ensure broad skill coverage
- **Critic Agreement**: Identify areas where critics disagree
- **Experimental vs LLM Alignment**: Spot hallucination patterns

## Integration with Build Orchestrator

Trained agents feed into the build orchestrator with improved routing:

1. **Skill-Based Routing**: AdaptiveRouter uses gym ratings
2. **Confidence Scoring**: High-rated agents get priority tasks  
3. **Continuous Learning**: Production feedback improves gym exercises
4. **Quality Prediction**: Pre-screen tasks based on agent ratings