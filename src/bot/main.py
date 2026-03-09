"""
Main entry point for Korea Stock Alert Bot
"""
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from telegram import Bot
from models.database import DatabaseManager
from handlers.bot_handler import BotHandler
from managers.alert_sender import AlertSender
from config import get_config, BOT_TOKEN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class KoreaStockAlertBot:
    """Main bot application"""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = DatabaseManager(self.config["database_path"])
        self.bot_handler: Optional[BotHandler] = None
        self.alert_sender: Optional[AlertSender] = None
        self.bot: Optional[Bot] = None
        
        # Graceful shutdown handling
        self._shutdown = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._shutdown = True
    
    async def initialize(self):
        """Initialize all bot components"""
        try:
            # Initialize database
            logger.info("Initializing database...")
            await self.db_manager.initialize()
            
            # Initialize bot
            logger.info("Initializing Telegram bot...")
            self.bot = Bot(token=BOT_TOKEN)
            
            # Initialize bot handler
            logger.info("Setting up bot handlers...")
            self.bot_handler = BotHandler(BOT_TOKEN, self.db_manager)
            
            # Initialize alert sender
            logger.info("Setting up alert sender...")
            self.alert_sender = AlertSender(self.bot, self.db_manager)
            
            # Link components
            self.bot_handler.set_alert_sender(self.alert_sender)
            
            logger.info("Bot initialization completed successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def run(self):
        """Run the bot application"""
        try:
            await self.initialize()
            
            # Start bot
            logger.info("Starting bot...")
            bot_task = asyncio.create_task(self.bot_handler.run())
            
            # Monitor for shutdown
            while not self._shutdown:
                await asyncio.sleep(1)
                
                # Check if bot task completed unexpectedly
                if bot_task.done():
                    exception = bot_task.exception()
                    if exception:
                        logger.error(f"Bot task failed: {exception}")
                        break
                    else:
                        logger.info("Bot task completed normally")
                        break
            
            # Graceful shutdown
            logger.info("Initiating shutdown...")
            bot_task.cancel()
            
            try:
                await bot_task
            except asyncio.CancelledError:
                logger.info("Bot task cancelled")
            
            if self.bot_handler:
                await self.bot_handler.stop()
            
            logger.info("Shutdown completed")
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise

def main():
    """Main function"""
    # Check if bot token is configured
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set your bot token: export TELEGRAM_BOT_TOKEN='your_token_here'")
        sys.exit(1)
    
    # Create and run bot
    bot_app = KoreaStockAlertBot()
    
    try:
        asyncio.run(bot_app.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()