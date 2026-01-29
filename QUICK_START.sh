#!/bin/bash
# Quick Start - Complete Composio + Instantly Setup
# Run this to finish campaign setup before Phase 1

set -e

echo "🚀 Nursery Enrichment Pipeline - Quick Start Setup"
echo "=================================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check for .env
if [ ! -f ".env" ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Check if INSTANTLY_API_KEY exists
if ! grep -q "INSTANTLY_API_KEY=" .env; then
    echo "❌ INSTANTLY_API_KEY not found in .env"
    exit 1
fi

echo "✓ Instantly API key found"
echo ""

# Check if COMPOSIO_API_KEY exists
if ! grep -q "COMPOSIO_API_KEY=" .env; then
    echo "⚠️  COMPOSIO_API_KEY not found in .env"
    echo ""
    echo "📋 Step 1: Get your Composio API Key"
    echo "   1. Visit: https://app.composio.dev/settings"
    echo "   2. Create account (if needed)"
    echo "   3. Go to Settings → API Keys"
    echo "   4. Create new API key"
    echo "   5. Copy the key"
    echo ""
    read -p "Enter your Composio API key: " composio_key
    
    if [ -z "$composio_key" ]; then
        echo "❌ No key provided"
        exit 1
    fi
    
    echo "" >> .env
    echo "# Composio Configuration" >> .env
    echo "COMPOSIO_API_KEY=$composio_key" >> .env
    
    echo "✅ Composio API key saved to .env"
    echo ""
else
    echo "✓ Composio API key found"
    echo ""
fi

# Step 2: Connect Instantly to Composio
echo "📋 Step 2: Connecting Instantly to Composio..."
echo ""

if ! grep -q "COMPOSIO_INSTANTLY_ACCOUNT_ID=" .env; then
    python scripts/connect_instantly.py
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Connection failed"
        echo "Check the error message above and try again"
        exit 1
    fi
else
    echo "✓ Instantly already connected (account ID found in .env)"
fi

echo ""
echo "📋 Step 3: Testing connection..."
echo ""

python scripts/test_instantly_connection.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Connection test failed"
    echo "Check the error message above"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ SETUP COMPLETE!"
echo "=================================================="
echo ""
echo "🎯 You're ready for Phase 1 implementation!"
echo ""
echo "Next steps:"
echo "  1. Review: PHASE_1_SETUP_CHECKLIST.md"
echo "  2. (Optional) Create test campaign: python scripts/create_test_campaign.py"
echo "  3. Move to Phase 1 implementation"
echo ""
echo "📊 Current Status:"
echo "   - Composio: Connected ✓"
echo "   - Instantly: Connected ✓"
echo "   - Client wrapper: Ready ✓"
echo "   - Test scripts: Ready ✓"
echo ""
