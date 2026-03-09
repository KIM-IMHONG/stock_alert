"""
Main bot handler for Korea Stock Alert Bot
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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

        # 종목 변경 시 호출되는 콜백 (WebSocket 구독 관리용)
        self.on_stock_added = None      # async def callback(stock_code: str)
        self.on_stock_removed = None    # async def callback(stock_code: str)

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
        self.application.add_handler(CommandHandler("status", self.status_command))

        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # 일반 텍스트 메시지 → 종목 검색 또는 설정 입력
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # 알 수 없는 /명령어 → 종목 검색 (예: /삼성, /카카오)
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self.handle_unknown_command)
        )

        # Error handler
        self.application.add_error_handler(self.error_handler)

        # 봇 시작 후 명령어 메뉴 등록
        self.application.post_init = self._set_bot_commands

    async def _set_bot_commands(self, application):
        """텔레그램 봇 명령어 메뉴 등록"""
        commands = [
            BotCommand("start", "봇 시작 / 초기화"),
            BotCommand("add", "종목 추가 (코드/이름/검색)"),
            BotCommand("remove", "종목 제거 (코드/이름)"),
            BotCommand("list", "내 관심종목 목록"),
            BotCommand("settings", "알림 임계값 설정"),
            BotCommand("status", "봇 상태 확인"),
            BotCommand("help", "도움말"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("봇 명령어 메뉴 등록 완료")
    
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
        """Handle /add [종목코드 또는 종목명] command"""
        try:
            user_id = update.effective_user.id

            if not context.args or len(context.args) == 0:
                await update.message.reply_text(
                    "💡 *종목 추가 방법:*\n\n"
                    "• /add 삼성 → 검색 결과에서 선택\n"
                    "• /add 005930 → 종목코드로 직접 추가\n"
                    "• 삼성 → 텍스트만 입력해도 검색",
                    parse_mode='Markdown'
                )
                return

            query = " ".join(context.args).strip()

            # 6자리 숫자면 종목코드로 바로 추가
            if self.user_manager.validate_stock_code(query):
                await self._add_stock_direct(update, user_id, query)
                return

            # 텍스트면 종목명 검색
            from ..utils.stock_search import get_stock_searcher
            searcher = get_stock_searcher()
            results = searcher.search(query, limit=8)

            if not results:
                await update.message.reply_text(
                    f"🔍 '{query}'에 대한 검색 결과가 없습니다.\n"
                    "6자리 종목코드로 직접 추가해보세요."
                )
                return

            if len(results) == 1:
                # 결과가 1개면 바로 추가
                await self._add_stock_direct(update, user_id, results[0][0])
                return

            # 여러 결과 → 인라인 키보드로 선택
            keyboard = []
            for code, name in results:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{name} ({code})",
                        callback_data=f"addstock_{code}"
                    )
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"🔍 *'{query}' 검색 결과*\n\n추가할 종목을 선택하세요:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error in add command: {e}")
            await update.message.reply_text(MESSAGES["error"])

    async def _add_stock_direct(self, update: Update, user_id: int, stock_code: str):
        """종목코드로 직접 추가"""
        success, message = await self.user_manager.add_stock_to_watchlist(
            user_id, stock_code
        )

        if success and self.on_stock_added:
            try:
                await self.on_stock_added(stock_code)
            except Exception as e:
                logger.error(f"종목 추가 콜백 오류: {e}")

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
    
    async def remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove [종목코드 또는 종목명] command"""
        try:
            user_id = update.effective_user.id

            if not context.args or len(context.args) == 0:
                # 관심종목을 인라인 버튼으로 보여주기
                watchlist = await self.user_manager.get_user_watchlist(user_id)
                if not watchlist:
                    await update.message.reply_text(MESSAGES["empty_watchlist"])
                    return

                from ..utils.stock_utils import get_stock_name
                keyboard = []
                for code in watchlist:
                    name = get_stock_name(code) or code
                    keyboard.append([
                        InlineKeyboardButton(
                            f"❌ {name} ({code})",
                            callback_data=f"rmstock_{code}"
                        )
                    ])
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    "🗑️ 제거할 종목을 선택하세요:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return

            query = " ".join(context.args).strip()

            # 6자리 숫자면 바로 제거
            stock_code = query
            if not self.user_manager.validate_stock_code(query):
                # 종목명으로 검색
                from ..utils.stock_search import get_stock_searcher
                searcher = get_stock_searcher()
                code = searcher.get_code(query)
                if code:
                    stock_code = code
                else:
                    results = searcher.search(query, limit=1)
                    if results:
                        stock_code = results[0][0]
                    else:
                        await update.message.reply_text(
                            f"❌ '{query}'에 해당하는 종목을 찾을 수 없습니다."
                        )
                        return

            success, message = await self.user_manager.remove_stock_from_watchlist(
                user_id, stock_code
            )

            if success and self.on_stock_removed:
                try:
                    await self.on_stock_removed(stock_code)
                except Exception as e:
                    logger.error(f"종목 제거 콜백 오류: {e}")

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
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - 봇 상태 확인"""
        try:
            user_id = update.effective_user.id
            stats = await self.user_manager.get_user_statistics(user_id)

            watchlist = await self.user_manager.get_user_watchlist(user_id)
            stock_list = ""
            if watchlist:
                from ..utils.stock_utils import get_stock_name
                for code in watchlist:
                    name = get_stock_name(code) or "알수없음"
                    stock_list += f"  • {name} ({code})\n"
            else:
                stock_list = "  없음\n"

            message = (
                f"📊 *봇 상태*\n\n"
                f"👤 관심종목: {stats['watchlist_count']}/{stats['watchlist_limit']}개\n"
                f"{stock_list}\n"
                f"⚙️ 알림 조건: 3분 내 ±{stats['alert_threshold']:.1f}% 이상 변동 시\n"
                f"🔔 실시간 모니터링 {'활성' if stats['watchlist_count'] > 0 else '대기중'}"
            )

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in status command: {e}")
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
                
            elif data.startswith("rmstock_"):
                # 인라인 버튼에서 종목 제거
                stock_code = data.replace("rmstock_", "")
                success, message = await self.user_manager.remove_stock_from_watchlist(
                    user_id, stock_code
                )

                if success and self.on_stock_removed:
                    try:
                        await self.on_stock_removed(stock_code)
                    except Exception as e:
                        logger.error(f"종목 제거 콜백 오류: {e}")

                keyboard = [
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")],
                    [InlineKeyboardButton("➕ 종목 추가", callback_data="help_add")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

            elif data.startswith("addstock_"):
                # 검색 결과에서 종목 선택 → 추가
                stock_code = data.replace("addstock_", "")
                success, message = await self.user_manager.add_stock_to_watchlist(
                    user_id, stock_code
                )

                if success and self.on_stock_added:
                    try:
                        await self.on_stock_added(stock_code)
                    except Exception as e:
                        logger.error(f"종목 추가 콜백 오류: {e}")

                keyboard = [
                    [InlineKeyboardButton("📋 내 종목 보기", callback_data="show_list")],
                    [InlineKeyboardButton("➕ 다른 종목 추가", callback_data="help_add")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

            elif data == "help_add":
                await query.edit_message_text(
                    "💡 *종목 추가 방법:*\n\n"
                    "• /add 삼성 → 검색 결과에서 선택\n"
                    "• /add 005930 → 종목코드로 직접 추가\n"
                    "• /삼성 → 바로 검색\n"
                    "• 삼성 → 텍스트만 입력해도 검색",
                    parse_mode='Markdown'
                )

            elif data == "help_remove":
                await query.edit_message_text(
                    "💡 *종목 제거 방법:*\n\n"
                    "• /remove → 목록에서 버튼으로 제거\n"
                    "• /remove 삼성전자 → 이름으로 제거\n"
                    "• /remove 005930 → 종목코드로 제거",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            if query:
                await query.answer("오류가 발생했습니다.")
    
    async def _search_and_show(self, update: Update, query: str):
        """종목 검색 후 인라인 키보드로 결과 표시"""
        from ..utils.stock_search import get_stock_searcher
        searcher = get_stock_searcher()

        # 6자리 숫자면 바로 종목 정보 표시
        if self.user_manager.validate_stock_code(query):
            name = searcher.get_name(query)
            if name:
                keyboard = [
                    [InlineKeyboardButton(
                        f"➕ {name} ({query}) 추가",
                        callback_data=f"addstock_{query}"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"🔍 *{name}* ({query})",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ '{query}' 종목을 찾을 수 없습니다.")
            return

        results = searcher.search(query, limit=8)

        if not results:
            await update.message.reply_text(
                f"🔍 '{query}'에 대한 검색 결과가 없습니다."
            )
            return

        keyboard = []
        for code, name in results:
            keyboard.append([
                InlineKeyboardButton(
                    f"➕ {name} ({code})",
                    callback_data=f"addstock_{code}"
                )
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🔍 *'{query}' 검색 결과*\n\n추가할 종목을 선택하세요:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """알 수 없는 /명령어를 종목 검색으로 처리 (예: /삼성 → '삼성' 검색)"""
        try:
            text = update.message.text.strip()
            # /삼성 → 삼성, /카카오 → 카카오
            query = text.lstrip('/')
            if query:
                await self._search_and_show(update, query)
        except Exception as e:
            logger.error(f"Error in handle_unknown_command: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages - 설정 입력 또는 종목 검색"""
        try:
            user_id = update.effective_user.id
            text = update.message.text.strip()

            # 설정값 입력 대기 중
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
                return

            # 일반 텍스트 → 종목 검색
            if text:
                await self._search_and_show(update, text)

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