#!/usr/bin/env python3
"""Weekly report generation script for ainews."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime, timedelta
from src.config import load_config, validate_config, ConfigError
from src.logger import setup_logging, get_logger
from src.storage.datastore import JSONDataStore
from src.summarizer.content_processor import ContentProcessor
from src.reports.generator import ReportGenerator
from src.reports.formatter import ReportFormatter


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate weekly report for ainews")
    
    parser.add_argument(
        "--week-start",
        type=str,
        help="Week start date (YYYY-MM-DD). Defaults to current week."
    )
    
    parser.add_argument(
        "--week-end",
        type=str,
        help="Week end date (YYYY-MM-DD). Defaults to current week."
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        help="Output file path. If not specified, uses default naming."
    )
    
    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "html", "json"],
        help="Output format. Overrides config setting."
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        help="Generate report focused on specific topic."
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include (for topic-focused reports)."
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview report without saving."
    )
    
    return parser.parse_args()


def main():
    """Main weekly report generation function."""
    try:
        args = parse_arguments()
        
        # Load configuration
        config = load_config()
        validate_config(config)
        
        # Setup logging
        logger = setup_logging(config.logging)
        logger.info("Starting weekly report generation")
        
        # Initialize components
        datastore = JSONDataStore(
            config.storage.data_dir,
            config.storage.backup_enabled
        )
        
        content_processor = ContentProcessor(config.llm_config)
        report_generator = ReportGenerator(datastore, content_processor)
        
        # Determine output format
        output_format = args.format or config.reporting.output_format
        report_formatter = ReportFormatter(output_format)
        
        if args.topic:
            # Generate topic-focused report
            logger.info(f"Generating topic-focused report for: {args.topic}")
            report_data = report_generator.generate_topic_focused_report(args.topic, args.days)
            
            if 'error' in report_data:
                print(f"Error: {report_data['error']}", file=sys.stderr)
                sys.exit(1)
            
            # Format topic report
            formatted_report = report_formatter.format_topic_report(report_data)
            report_title = f"Topic Report: {args.topic}"
            
        else:
            # Generate regular weekly report
            logger.info("Generating weekly report")
            
            # Generate the report
            weekly_report = report_generator.generate_weekly_report(args.week_start, args.week_end)
            
            # Format the report
            formatted_report = report_formatter.format_weekly_report(weekly_report)
            report_title = f"Weekly Report: {weekly_report.week_start} to {weekly_report.week_end}"
        
        # Handle output
        if args.preview:
            # Preview mode - just print to console
            print(f"\n=== {report_title} ===")
            print(formatted_report)
        else:
            # Save to file
            if args.output_file:
                output_path = Path(args.output_file)
            else:
                # Generate default filename
                if args.topic:
                    filename = f"topic-{args.topic.lower().replace(' ', '-')}-{datetime.now().strftime('%Y-%m-%d')}"
                else:
                    week_start = args.week_start or datetime.now().strftime('%Y-%m-%d')
                    filename = f"weekly-report-{week_start}"
                
                # Add extension based on format
                extensions = {"markdown": ".md", "html": ".html", "json": ".json"}
                extension = extensions.get(output_format, ".txt")
                
                output_path = Path(config.storage.data_dir) / "reports" / f"{filename}{extension}"
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write report to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_report)
            
            logger.info(f"Report saved to: {output_path}")
            print(f"Report saved to: {output_path}")
            
            # Also save JSON version if not already JSON
            if not args.topic and output_format != "json":
                json_path = output_path.with_suffix('.json')
                datastore.save_weekly_report(weekly_report)
                logger.info(f"JSON data saved to: {json_path}")
        
        # Print summary statistics
        if not args.topic and 'weekly_report' in locals():
            print(f"\n=== Report Summary ===")
            print(f"Period: {weekly_report.week_start} to {weekly_report.week_end}")
            print(f"Total articles: {weekly_report.total_articles}")
            print(f"Topics covered: {len(weekly_report.articles_by_topic)}")
            
            if weekly_report.articles_by_topic:
                print(f"Top topics:")
                sorted_topics = sorted(weekly_report.articles_by_topic.items(), 
                                     key=lambda x: x[1], reverse=True)
                for topic, count in sorted_topics[:5]:
                    print(f"  - {topic}: {count} articles")
        
        logger.info("Weekly report generation completed successfully")
        
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nReport generation interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Unexpected error during report generation: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()