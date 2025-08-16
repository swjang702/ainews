# AI News Curator

An AI-powered news curation system that automatically crawls tech websites, filters articles based on interest topics, and generates summaries using LLM APIs.

## Features

- **Automated Crawling**: Daily crawling of Hacker News and LWN.net
- **Topic Filtering**: Smart filtering based on configurable interest topics
- **AI Summarization**: Generates concise summaries using Claude or OpenAI
- **Duplicate Detection**: Prevents processing of duplicate articles
- **Weekly Reports**: Comprehensive weekly analysis and trends
- **Multiple Output Formats**: Markdown, HTML, and JSON reports

## Quick Start

### 1. Installation

```bash
# Clone the repository (if from git)
# cd ainews

# Install dependencies
pip install -r requirements.txt

# Test the setup
python test_setup.py
```

### 2. Configuration

1. Set up your API key:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
# or
export OPENAI_API_KEY="your-api-key-here"
```

2. Edit `config/config.yaml` to customize:
   - Interest topics
   - Website settings
   - LLM configuration
   - Output preferences

### 3. Run Daily Crawl

```bash
python scripts/daily_crawl.py
```

### 4. Generate Weekly Report

```bash
# Generate current week report
python scripts/weekly_report.py

# Generate report for specific week
python scripts/weekly_report.py --week-start 2025-01-13 --week-end 2025-01-19

# Generate topic-focused report
python scripts/weekly_report.py --topic "Rust" --days 7

# Preview without saving
python scripts/weekly_report.py --preview
```

## Configuration

The system is configured via `config/config.yaml`. Key sections:

- **interest_topics**: List of topics to filter for
- **websites**: Website crawling settings
- **llm_config**: LLM provider and model settings
- **filtering**: Relevance thresholds and limits
- **reporting**: Output format and report settings

## Architecture

- **Modular Design**: Clear separation of concerns
- **Error Handling**: Comprehensive retry logic and graceful degradation
- **Storage**: JSON-based file storage with atomic operations
- **Scalable**: Easy to add new websites or topics

## Project Structure

```
ainews/
├── src/                    # Source code
│   ├── crawler.py         # Web crawling logic
│   ├── filters/           # Topic filtering
│   ├── summarizer/        # LLM integration
│   ├── storage/           # Data persistence
│   └── reports/           # Report generation
├── scripts/               # Entry points
├── config/                # Configuration files
├── data/                  # Stored articles and reports
└── logs/                  # Application logs
```

## Automation

Set up cron jobs for automated operation:

```bash
# Daily crawl at 9 AM
0 9 * * * cd /path/to/ainews && python scripts/daily_crawl.py

# Weekly report on Sundays at 8 PM
0 20 * * 0 cd /path/to/ainews && python scripts/weekly_report.py
```

## Dependencies

- Python 3.8+
- requests, BeautifulSoup4, PyYAML
- anthropic or openai (based on LLM choice)

## Future Direction

- How smart is the scoring system? 
- How reliable of the source and author? (Add author information into the report)
- What about getting feedbacks that user give and learn it for smarter curation?
