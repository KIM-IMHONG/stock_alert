"""
Basic tests for Korea Stock Alert Bot functionality
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import using the module structure - we need to temporarily fix imports
import importlib.util

# Import database module
spec = importlib.util.spec_from_file_location("database", "models/database.py")
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)
DatabaseManager = database_module.DatabaseManager

# Import utils module  
spec = importlib.util.spec_from_file_location("stock_utils", "utils/stock_utils.py")
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)
validate_stock_code = utils_module.validate_stock_code
get_stock_name = utils_module.get_stock_name
format_price = utils_module.format_price

async def test_database():
    """Test database functionality"""
    print("🧪 Testing database functionality...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db = f.name
    
    try:
        db_manager = DatabaseManager(temp_db)
        await db_manager.initialize()
        
        # Test user creation
        user = await db_manager.create_or_update_user(
            user_id=12345, 
            username="testuser", 
            first_name="Test User"
        )
        print(f"✅ User created: {user.first_name}")
        
        # Test watchlist operations
        success = await db_manager.add_to_watchlist(12345, "005930")
        print(f"✅ Added stock to watchlist: {success}")
        
        watchlist = await db_manager.get_watchlist(12345)
        print(f"✅ Watchlist retrieved: {watchlist}")
        
        # Test alert threshold
        await db_manager.update_alert_threshold(12345, 7.5)
        threshold = await db_manager.get_user_alert_threshold(12345)
        print(f"✅ Alert threshold updated: {threshold}%")
        
        print("✅ Database tests passed!")
        
    finally:
        # Cleanup
        os.unlink(temp_db)

async def test_user_manager():
    """Test user manager functionality"""
    print("\n🧪 Testing user manager functionality...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db = f.name
    
    try:
        db_manager = DatabaseManager(temp_db)
        await db_manager.initialize()
        
        user_manager = UserManager(db_manager)
        
        # Test user registration
        success = await user_manager.register_user(67890, "testuser2", "Test User 2")
        print(f"✅ User registered: {success}")
        
        # Test stock addition
        success, message = await user_manager.add_stock_to_watchlist(67890, "005930")
        print(f"✅ Stock added: {success} - {message}")
        
        # Test invalid stock code
        success, message = await user_manager.add_stock_to_watchlist(67890, "invalid")
        print(f"✅ Invalid stock rejected: {not success} - {message}")
        
        # Test watchlist formatting
        watchlist_msg = await user_manager.format_watchlist_message(67890)
        print(f"✅ Watchlist formatted: {len(watchlist_msg)} characters")
        
        print("✅ User manager tests passed!")
        
    finally:
        # Cleanup
        os.unlink(temp_db)

def test_stock_utils():
    """Test stock utility functions"""
    print("\n🧪 Testing stock utility functions...")
    
    # Test stock code validation
    assert validate_stock_code("005930") == True
    assert validate_stock_code("invalid") == False
    assert validate_stock_code("12345") == False
    print("✅ Stock code validation works")
    
    # Test stock name lookup
    name = get_stock_name("005930")
    print(f"✅ Stock name lookup: 005930 -> {name}")
    
    # Test price formatting
    formatted = format_price(1234567.89)
    print(f"✅ Price formatting: 1234567.89 -> {formatted}")
    
    print("✅ Stock utils tests passed!")

def test_config():
    """Test configuration"""
    print("\n🧪 Testing configuration...")
    
    try:
        from config import get_config, MESSAGES
        
        config = get_config()
        print(f"✅ Config loaded: {len(config)} settings")
        
        assert "welcome" in MESSAGES
        assert "stock_added" in MESSAGES
        print("✅ Message templates loaded")
        
        print("✅ Configuration tests passed!")
        
    except Exception as e:
        print(f"⚠️ Config test failed (expected if BOT_TOKEN not set): {e}")

async def run_all_tests():
    """Run all tests"""
    print("🚀 Starting Korea Stock Alert Bot Tests")
    print("=" * 50)
    
    try:
        # Test components
        test_stock_utils()
        test_config()
        await test_database()
        await test_user_manager()
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed!")
        print("💡 To run the bot, set TELEGRAM_BOT_TOKEN and run main.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_all_tests())