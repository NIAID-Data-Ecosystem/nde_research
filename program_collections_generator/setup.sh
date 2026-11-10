#!/bin/bash
"""
Setup script for Program Collections Automation

This script helps set up the automation environment and validates the setup.
"""

set -e

echo "🚀 Setting up Program Collections Automation..."
echo "================================================"

# Check Python version
echo "📋 Checking Python version..."
python3 --version || {
    echo "❌ Python 3 is required but not found"
    exit 1
}

# Install dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Validate data files
echo "📂 Checking data files..."
required_files=(
    "data/approved_for_prod.txt"
    "data/control_transferred.txt"
    "data/NIH_activity_codes.csv"
    "data/NIH_IC_codes.tsv"
    "data/Program Collections.xlsx"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ Found: $file"
    else
        echo "⚠️  Missing: $file"
    fi
done

# Test the automation
echo "🧪 Running automation tests..."
python3 test_automation.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Run manual test: python3 program_collections_automation.py --environment staging"
    echo "2. Deploy GitHub Actions workflow to automate scheduling"
    echo "3. Configure webhook endpoint for real-time triggers"
    echo ""
    echo "For more information, see README.md and AUTOMATION_REPORT.md"
else
    echo "❌ Setup validation failed. Please check the errors above."
    exit 1
fi
