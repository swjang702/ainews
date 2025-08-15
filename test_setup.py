#!/usr/bin/env python3
"""Test script to verify setup."""

import sys
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all critical imports."""
    try:
        from src.config import load_config, validate_config
        from src.logger import setup_logging
        from src.models import Article
        from src.storage.datastore import JSONDataStore
        from src.filters.topic_filter import TopicFilter
        from src.crawler import WebCrawler
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    try:
        # Set mock API key
        os.environ['ANTHROPIC_API_KEY'] = 'test-key'
        
        from src.config import load_config, validate_config
        config = load_config()
        validate_config(config)
        print("✓ Configuration loads successfully")
        print(f"  - Topics: {len(config.interest_topics)}")
        print(f"  - Websites: {len(config.websites)}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    try:
        from src.models import Article
        from src.filters.topic_filter import TopicFilter
        from src.logger import setup_logging
        from src.config import LoggingConfig
        
        # Setup logging
        setup_logging(LoggingConfig())
        
        # Test article creation
        article = Article.create("Test Rust Article", "https://example.com", "test", "Rust programming content")
        
        # Test topic filtering
        topics = ["Rust", "AI", "Security"]
        filter = TopicFilter(topics, 0.2)
        
        # Test filtering
        filtered = filter.filter_articles([article])
        
        print("✓ Basic functionality works")
        print(f"  - Article created: {article.title}")
        print(f"  - Topics matched: {filtered[0].related_topics if filtered else 'None'}")
        return True
    except Exception as e:
        print(f"✗ Functionality error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=== AI News Curator Setup Test ===\n")
    
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Basic Functionality Test", test_basic_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        success = test_func()
        results.append(success)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=== Test Summary ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Set your ANTHROPIC_API_KEY environment variable")
        print("2. Run: python scripts/daily_crawl.py")
        print("3. Run: python scripts/weekly_report.py --preview")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()