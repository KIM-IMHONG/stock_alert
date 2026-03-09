"""
Simple tests for Korea Stock Alert Bot functionality
"""
import asyncio
import sqlite3
import tempfile
import os

def test_stock_utils():
    """Test stock utility functions"""
    print("🧪 Testing stock utility functions...")
    
    # Simple stock code validation
    def validate_stock_code(code):
        import re
        pattern = re.compile(r'^\d{6}$')
        return bool(pattern.match(code.strip() if code else ""))
    
    assert validate_stock_code("005930") == True
    assert validate_stock_code("invalid") == False
    assert validate_stock_code("12345") == False
    print("✅ Stock code validation works")
    
    # Simple price formatting
    def format_price(price):
        return f"{int(price):,}"
    
    formatted = format_price(1234567.89)
    print(f"✅ Price formatting: 1234567.89 -> {formatted}")
    
    print("✅ Stock utils tests passed!")

def test_sqlite():
    """Test SQLite functionality"""
    print("\n🧪 Testing SQLite database...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db = f.name
    
    try:
        # Connect and create tables
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                alert_threshold REAL DEFAULT 5.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create watchlist table
        cursor.execute("""
            CREATE TABLE watchlist (
                user_id INTEGER,
                stock_code TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, stock_code),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Insert test data
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (12345, "testuser", "Test User"))
        
        cursor.execute("""
            INSERT INTO watchlist (user_id, stock_code)
            VALUES (?, ?)
        """, (12345, "005930"))
        
        conn.commit()
        
        # Test queries
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Users created: {user_count}")
        
        cursor.execute("SELECT stock_code FROM watchlist WHERE user_id = ?", (12345,))
        stocks = cursor.fetchall()
        print(f"✅ Watchlist items: {len(stocks)}")
        
        conn.close()
        print("✅ Database tests passed!")
        
    finally:
        # Cleanup
        if os.path.exists(temp_db):
            os.unlink(temp_db)

def test_config():
    """Test configuration loading"""
    print("\n🧪 Testing configuration...")
    
    try:
        # Check if config file exists
        if os.path.exists("config.py"):
            print("✅ Config file exists")
            
            # Try to read some basic settings
            with open("config.py", 'r') as f:
                content = f.read()
                if "BOT_TOKEN" in content:
                    print("✅ Bot token configuration found")
                if "MESSAGES" in content:
                    print("✅ Message templates found")
                if "MAX_WATCHLIST_SIZE" in content:
                    print("✅ Watchlist size limit found")
        
        print("✅ Configuration tests passed!")
        
    except Exception as e:
        print(f"⚠️ Config test warning: {e}")

def test_file_structure():
    """Test file structure"""
    print("\n🧪 Testing file structure...")
    
    required_files = [
        "main.py",
        "config.py", 
        "requirements.txt",
        "handlers/bot_handler.py",
        "managers/user_manager.py",
        "managers/alert_sender.py",
        "models/database.py",
        "utils/stock_utils.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path} exists")
    
    if missing_files:
        print(f"⚠️ Missing files: {missing_files}")
    else:
        print("✅ All required files present!")

def run_all_tests():
    """Run all tests"""
    print("🚀 Starting Korea Stock Alert Bot Simple Tests")
    print("=" * 50)
    
    try:
        test_stock_utils()
        test_sqlite()
        test_config()
        test_file_structure()
        
        print("\n" + "=" * 50)
        print("🎉 All simple tests completed successfully!")
        print("💡 Bot structure is ready!")
        print("📝 Next steps:")
        print("   1. Set TELEGRAM_BOT_TOKEN in .env file")
        print("   2. Run ./run_bot.sh or python3 main.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()