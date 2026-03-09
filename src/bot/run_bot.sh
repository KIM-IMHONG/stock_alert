#!/bin/bash

# Korea Stock Alert Bot Startup Script

echo "🤖 Starting Korea Stock Alert Bot..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "📝 Please create .env file based on .env.example"
    echo "💡 Set your TELEGRAM_BOT_TOKEN in the .env file"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if bot token is set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN is not set in .env file"
    echo "💡 Please add your bot token to .env file"
    exit 1
fi

echo "🚀 Starting bot..."
python3 main.py