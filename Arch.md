# Architecture Design

## Overview

AI-powered news curation system using **Modular Monolith with Plugin System** architecture. This design balances MVP simplicity with maintainability and extensibility.

## Core Architecture

### Design Principles
- **MVP (Minimum Viable Product)**: Simple deployment, no complex infrastructure
- **Divide & Conquer**: Clear separation of concerns, testable modules
- **Extensible**: Easy to add new websites or topics
- **Maintainable**: Single codebase, clear data flow

### System Components

```
ainews/
├── src/
│   ├── crawler.py    # Single crawler with methods for each website
│   ├── filters/      # Topic filtering logic  
│   │   ├── topic_filter.py   # Keyword-based filtering
│   │   └── relevance.py      # Scoring algorithms
│   ├── summarizer/   # LLM integration
│   │   ├── llm_client.py     # API wrapper (OpenAI/Anthropic)
│   │   └── content_processor.py
│   ├── storage/      # JSON-based data persistence
│   │   ├── datastore.py      # Main storage interface
│   │   └── duplicate_detector.py
│   └── reports/      # Weekly report generation
│       ├── generator.py      # Report creation logic
│       └── formatter.py      # Output formatting
├── data/             # Stored articles and reports
│   ├── articles/     # Daily article collections
│   ├── reports/      # Weekly reports
│   └── metadata/     # State tracking, processed URLs
├── config/           # Configuration files
│   └── config.yaml   # Topics, websites, settings
└── scripts/          # Entry points
    ├── daily_crawl.py    # Daily automation script
    └── weekly_report.py  # Weekly report generation
```

## Data Flow

### Daily Pipeline
```
Websites → Crawler → Raw Articles → Filter → Relevant Articles → Summarizer → Processed Articles → Storage
```

### Weekly Pipeline  
```
Storage → Analyzer → Weekly Report → Delivery
```

## Data Models

### Article Data Structure
```json
{
  "id": "hash of url",
  "title": "Article Title", 
  "url": "https://...",
  "source": "hackernews|lwn",
  "discovered_date": "2025-01-15",
  "content_hash": "for duplicate detection",
  "summary": "AI-generated summary",
  "related_topics": ["rust", "ebpf"],
  "relevance_score": 0.85
}
```

### Storage Structure
```
data/
├── articles/
│   ├── 2025-01-15.json    # Daily article collections
│   └── 2025-01-16.json
├── reports/
│   ├── week-2025-01-13.md  # Weekly reports
│   └── week-2025-01-20.md
└── metadata/
    ├── last_crawl.json     # Tracking state
    └── processed_urls.json # Duplicate prevention
```

## Technology Stack

- **Language**: Python (web scraping, AI APIs, simple deployment)
- **Web Scraping**: requests + BeautifulSoup (simple) or playwright (if JS needed)
- **AI/LLM**: OpenAI API or Anthropic API
- **Storage**: JSON files with file-based structure
- **Scheduling**: cron jobs + Python scripts
- **Configuration**: YAML config files

## Key Features

### Duplicate Detection
- Content hashing to prevent re-processing
- URL tracking in metadata

### Error Handling
- Retry logic for network failures (exponential backoff)
- Graceful degradation if one website fails
- API rate limiting handling
- Comprehensive logging

### Modularity
- Single crawler file with method-based separation
- Clear component interfaces
- Independent testing of modules

## Operational Flow

### Daily Operation (`daily_crawl.py`)
1. Load configuration (topics, websites, API keys)
2. For each website: crawl → filter → summarize → store
3. Maintain state file for last-crawled timestamps
4. Log results for monitoring

### Weekly Operation (`weekly_report.py`)
1. Analyze articles from past 7 days
2. Group by topics, identify trends
3. Generate formatted report (markdown/HTML)
4. Save to reports/ directory

## Benefits

- ✅ **Simple Deployment**: Single Python application
- ✅ **Clear Separation**: Testable, maintainable modules
- ✅ **Extensible**: Easy to add new sites/topics
- ✅ **Reliable**: File-based storage, cron scheduling
- ✅ **Version Control**: Human-readable JSON storage
- ✅ **MVP-Ready**: Minimal complexity, maximum value