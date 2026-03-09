"""
Main bot handler for Korea Stock Alert Bot
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from ..models.database import DatabaseManager
from ..managers.user_manager import UserManager
from ..managers.alert_sender import AlertSender
from ..config import MESSAGES

logger = logging.getLogger(__name__)

class BotHandler:
    """Main bot handler managing all telegram interactions"""
    
    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        self.bot_token = bot_token
        self.db_manager = db_manager
        self.user_manager = UserManager(db_manager)
        self.application = Application.builder().token(bot_token).build()
        self.alert_sender = None  # Will be set after bot is initialized
        
        # User states for conversation flow
        self.waiting_for_settings = set()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("add", self.add_command))
        self.application.add_handler(CommandHandler("remove", self.remove_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handler for settings input
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user = update.effective_user
            
            # Register user
            success = await self.user_manager.register_user(
                user.id, user.username, user.first_name or ""
            )
            
            if success:
                # Create welcome keyboard
                keyboard = [
                    [InlineKeyboardButton("📈 종목 추가", callback_data="help_add")],
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")],
                    [InlineKeyboardButton("⚙️ 알림 설정", callback_data="show_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    MESSAGES["welcome"],
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(MESSAGES["error"])
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text(MESSAGES["error"])
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(MESSAGES["help"], parse_mode='Markdown')
    
    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add [stock_code] command"""
        try:
            user_id = update.effective_user.id
            
            # Check if stock code provided
            if not context.args or len(context.args) == 0:
                await update.message.reply_text(
                    "💡 사용법: /add [종목코드]\n예시: /add 005930"
                )
                return
            
            stock_code = context.args[0].strip()
            
            # Add stock to watchlist
            success, message = await self.user_manager.add_stock_to_watchlist(
                user_id, stock_code
            )
            
            # Show updated watchlist if successful
            if success:
                # Create quick action keyboard
                keyboard = [
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")],
                    [InlineKeyboardButton("➕ 다른 종목 추가", callback_data="help_add")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    message, 
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in add command: {e}")
            await update.message.reply_text(MESSAGES["error"])
    
    async def remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove [stock_code] command"""
        try:
            user_id = update.effective_user.id
            
            # Check if stock code provided
            if not context.args or len(context.args) == 0:
                await update.message.reply_text(
                    "💡 사용법: /remove [종목코드]\n예시: /remove 005930"
                )
                return
            
            stock_code = context.args[0].strip()
            
            # Remove stock from watchlist
            success, message = await self.user_manager.remove_stock_from_watchlist(
                user_id, stock_code
            )
            
            # Show updated watchlist if successful
            if success:
                keyboard = [
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")],
                    [InlineKeyboardButton("➕ 종목 추가", callback_data="help_add")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in remove command: {e}")
            await update.message.reply_text(MESSAGES["error"])
    
    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command"""
        try:
            user_id = update.effective_user.id
            message = await self.user_manager.format_watchlist_message(user_id)
            
            # Create action keyboard
            keyboard = [
                [InlineKeyboardButton("➕ 종목 추가", callback_data="help_add")],
                [InlineKeyboardButton("➖ 종목 제거", callback_data="help_remove")],
                [InlineKeyboardButton("⚙️ 알림 설정", callback_data="show_settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in list command: {e}")
            await update.message.reply_text(MESSAGES["error"])
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        try:
            user_id = update.effective_user.id
            
            if context.args and len(context.args) > 0:
                # User provided threshold directly
                try:
                    threshold = float(context.args[0])
                    success, message = await self.user_manager.update_alert_settings(
                        user_id, threshold
                    )
                    await update.message.reply_text(message, parse_mode='Markdown')
                except ValueError:
                    await update.message.reply_text(
                        MESSAGES["invalid_threshold"],
                        parse_mode='Markdown'
                    )
            else:
                # Show current settings and prompt for input
                message = await self.user_manager.get_alert_settings_message(user_id)
                
                keyboard = [
                    [
                        InlineKeyboardButton("3%", callback_data="set_threshold_3"),
                        InlineKeyboardButton("5%", callback_data="set_threshold_5"),
                        InlineKeyboardButton("10%", callback_data="set_threshold_10")
                    ],
                    [InlineKeyboardButton("직접 입력", callback_data="input_threshold")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error in settings command: {e}")
            await update.message.reply_text(MESSAGES["error"])
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            data = query.data
            
            if data == "show_list":
                message = await self.user_manager.format_watchlist_message(user_id)
                keyboard = [
                    [InlineKeyboardButton("➕ 종목 추가", callback_data="help_add")],
                    [InlineKeyboardButton("⚙️ 알림 설정", callback_data="show_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            elif data == "show_settings":
                message = await self.user_manager.get_alert_settings_message(user_id)
                keyboard = [
                    [
                        InlineKeyboardButton("3%", callback_data="set_threshold_3"),
                        InlineKeyboardButton("5%", callback_data="set_threshold_5"),
                        InlineKeyboardButton("10%", callback_data="set_threshold_10")
                    ],
                    [InlineKeyboardButton("직접 입력", callback_data="input_threshold")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            elif data.startswith("set_threshold_"):
                threshold = float(data.split("_")[-1])
                success, message = await self.user_manager.update_alert_settings(
                    user_id, threshold
                )
                
                keyboard = [
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            elif data == "input_threshold":
                self.waiting_for_settings.add(user_id)
                await query.edit_message_text(
                    "💡 알림 기준을 입력해주세요 (1-50 사이의 숫자)\n예: 7",
                    parse_mode='Markdown'
                )
                
            elif data == "help_add":
                await query.edit_message_text(
                    "💡 종목 추가 방법:\n/add [종목코드]\n\n예시: /add 005930",
                    parse_mode='Markdown'
                )
                
            elif data == "help_remove":
                await query.edit_message_text(
                    "💡 종목 제거 방법:\n/remove [종목코드]\n\n예시: /remove 005930",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await query.answer("오류가 발생했습니다.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (mainly for settings input)"""
        try:
            user_id = update.effective_user.id
            text = update.message.text.strip()
            
            if user_id in self.waiting_for_settings:
                self.waiting_for_settings.remove(user_id)
                
                try:
                    threshold = float(text)
                    success, message = await self.user_manager.update_alert_settings(
                        user_id, threshold
                    )
                    
                    keyboard = [
                        [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        message,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                except ValueError:
                    await update.message.reply_text(
                        MESSAGES["invalid_threshold"],
                        parse_mode='Markdown'
                    )
            
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Error in bot handler: {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(MESSAGES["error"])
            except:
                pass  # Ignore if can't send error message
    
    def set_alert_sender(self, alert_sender: AlertSender):
        """Set alert sender after bot initialization"""
        self.alert_sender = alert_sender
    
    async def run(self):
        """Run the bot"""
        logger.info("Starting Korea Stock Alert Bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Keep running
        await self.application.updater.idle()
    
    async def stop(self):
        """Stop the bot"""
        logger.info("Stopping Korea Stock Alert Bot...")
        await self.application.stop()
        await self.application.shutdown()