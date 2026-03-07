Read PLAN.md and PRD.md. Then implement all code changes described in PLAN.md Phase 1 through Phase 4.

Phase 1: Tracker + Data Layer
- Create src/xhs_creator/tracker.py with TrackerStore class
- Create src/xhs_creator/commands/rate_cmd.py
- Create src/xhs_creator/commands/history_cmd.py  
- Create src/xhs_creator/commands/stats_cmd.py
- Modify src/xhs_creator/formatter.py to add format_trace_row, format_history_table, format_stats_report
- Register new commands in src/xhs_creator/cli.py

Phase 2: Analyzer + Optimizer
- Create src/xhs_creator/analyzer.py
- Create src/xhs_creator/optimizer.py with PromptVersionStore
- Create src/xhs_creator/commands/prompt_cmd.py
- Modify src/xhs_creator/prompts.py to add BUILTIN_PROMPTS and get_prompt()

Phase 3: Smart Topic Recommender
- Create src/xhs_creator/recommender.py with TrendCollector, UserProfile, TopicScorer, Recommender
- Create src/xhs_creator/commands/recommend_cmd.py
- Create src/xhs_creator/commands/trends_cmd.py
- Create src/xhs_creator/commands/profile_cmd.py

Phase 4: Integration
- Modify src/xhs_creator/commands/publish_cmd.py to auto-register with tracker after publish
- Connect recommender with tracker data
- Modify src/xhs_creator/commands/topic_cmd.py to add --smart flag

Write ALL files directly. Follow the exact function signatures from PLAN.md. After writing all files, run existing tests to verify nothing is broken.
