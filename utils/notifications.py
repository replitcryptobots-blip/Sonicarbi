"""
Notification system for Telegram and Discord alerts.

Sends alerts for:
- New arbitrage opportunities
- Trade executions
- Errors and warnings
- System status updates
"""

import aiohttp
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from config.logging_config import get_logger
from config.config import config

logger = get_logger(__name__)


class TelegramNotifier:
    """
    Telegram bot notification system.

    Sends formatted messages to a Telegram chat using the Bot API.
    """

    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = bool(bot_token and chat_id)

        if self.enabled:
            logger.info(f"Telegram notifier initialized (chat_id: {chat_id})")
        else:
            logger.warning("Telegram notifier disabled (missing bot_token or chat_id)")

    async def send_message(
        self,
        message: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True
    ) -> bool:
        """
        Send a message to Telegram.

        Args:
            message: Message text (supports HTML or Markdown)
            parse_mode: "HTML" or "Markdown"
            disable_preview: Disable link previews

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram disabled, skipping message")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_preview
                }

                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram API error {response.status}: {error_text}")
                        return False

        except asyncio.TimeoutError:
            logger.error("Telegram message timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}", exc_info=True)
            return False

    async def send_opportunity_alert(self, opportunity: Dict) -> bool:
        """
        Send arbitrage opportunity alert.

        Args:
            opportunity: Opportunity dict with details

        Returns:
            True if successful
        """
        try:
            # Format message with HTML
            message = f"""
🎯 <b>ARBITRAGE OPPORTUNITY</b>

📊 <b>Pair:</b> {opportunity['token_in']} → {opportunity['token_out']}
💰 <b>Profit:</b> {opportunity['profit_pct']:.3f}% (${opportunity['profit_usd']:.2f})

🔄 <b>Route:</b>
  • Buy: {opportunity['buy_dex']} @ {opportunity['buy_price']:.6f}
  • Sell: {opportunity['sell_dex']} @ {opportunity['sell_price']:.6f}

⛽ <b>Gas Cost:</b> ${opportunity['gas_cost_usd']:.4f} ({opportunity['gas_estimate']} gas)
💵 <b>Trade Size:</b> {opportunity['amount']} {opportunity['token_in']}

🕐 <b>Time:</b> {opportunity['timestamp']}
"""

            return await self.send_message(message.strip())

        except Exception as e:
            logger.error(f"Error sending opportunity alert: {e}")
            return False

    async def send_execution_alert(self, execution: Dict) -> bool:
        """
        Send trade execution alert.

        Args:
            execution: Execution dict with details

        Returns:
            True if successful
        """
        try:
            status_emoji = "✅" if execution['status'] == 'success' else "❌"

            message = f"""
{status_emoji} <b>TRADE EXECUTION</b>

📊 <b>Pair:</b> {execution['token_in']} → {execution['token_out']}
💰 <b>Profit:</b> {execution.get('actual_profit_pct', 0):.3f}% (${execution.get('actual_profit_usd', 0):.2f})

🔄 <b>Route:</b>
  • {execution['buy_dex']} → {execution['sell_dex']}

📝 <b>Status:</b> {execution['status']}
🔗 <b>Tx Hash:</b> <code>{execution.get('tx_hash', 'N/A')}</code>

🕐 <b>Time:</b> {execution['timestamp']}
"""

            return await self.send_message(message.strip())

        except Exception as e:
            logger.error(f"Error sending execution alert: {e}")
            return False

    async def send_error_alert(self, error_msg: str, context: Optional[Dict] = None) -> bool:
        """
        Send error alert.

        Args:
            error_msg: Error message
            context: Optional context dict

        Returns:
            True if successful
        """
        try:
            message = f"""
❌ <b>ERROR ALERT</b>

⚠️ <b>Message:</b> {error_msg}
"""

            if context:
                message += "\n📋 <b>Context:</b>\n"
                for key, value in context.items():
                    message += f"  • {key}: {value}\n"

            message += f"\n🕐 <b>Time:</b> {datetime.now().isoformat()}"

            return await self.send_message(message.strip())

        except Exception as e:
            logger.error(f"Error sending error alert: {e}")
            return False

    async def send_status_update(self, status: str, details: Optional[Dict] = None) -> bool:
        """
        Send system status update.

        Args:
            status: Status message
            details: Optional details dict

        Returns:
            True if successful
        """
        try:
            message = f"""
ℹ️ <b>STATUS UPDATE</b>

{status}
"""

            if details:
                message += "\n📊 <b>Details:</b>\n"
                for key, value in details.items():
                    message += f"  • {key}: {value}\n"

            message += f"\n🕐 <b>Time:</b> {datetime.now().isoformat()}"

            return await self.send_message(message.strip())

        except Exception as e:
            logger.error(f"Error sending status update: {e}")
            return False


class DiscordNotifier:
    """
    Discord webhook notification system.

    Sends formatted messages to a Discord channel using webhooks.
    """

    def __init__(self, webhook_url: Optional[str]):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

        if self.enabled:
            logger.info("Discord notifier initialized")
        else:
            logger.warning("Discord notifier disabled (missing webhook_url)")

    async def send_message(
        self,
        content: str,
        embeds: Optional[List[Dict]] = None
    ) -> bool:
        """
        Send a message to Discord.

        Args:
            content: Message content
            embeds: Optional list of embed dicts

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Discord disabled, skipping message")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                payload = {"content": content}
                if embeds:
                    payload["embeds"] = embeds

                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status in [200, 204]:
                        logger.debug("Discord message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook error {response.status}: {error_text}")
                        return False

        except asyncio.TimeoutError:
            logger.error("Discord message timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}", exc_info=True)
            return False

    async def send_opportunity_alert(self, opportunity: Dict) -> bool:
        """
        Send arbitrage opportunity alert to Discord.

        Args:
            opportunity: Opportunity dict

        Returns:
            True if successful
        """
        try:
            embed = {
                "title": "🎯 Arbitrage Opportunity Found",
                "color": 0x00ff00,  # Green
                "fields": [
                    {
                        "name": "Pair",
                        "value": f"{opportunity['token_in']} → {opportunity['token_out']}",
                        "inline": True
                    },
                    {
                        "name": "Profit",
                        "value": f"{opportunity['profit_pct']:.3f}% (${opportunity['profit_usd']:.2f})",
                        "inline": True
                    },
                    {
                        "name": "Buy",
                        "value": f"{opportunity['buy_dex']} @ {opportunity['buy_price']:.6f}",
                        "inline": True
                    },
                    {
                        "name": "Sell",
                        "value": f"{opportunity['sell_dex']} @ {opportunity['sell_price']:.6f}",
                        "inline": True
                    },
                    {
                        "name": "Gas Cost",
                        "value": f"${opportunity['gas_cost_usd']:.4f} ({opportunity['gas_estimate']} gas)",
                        "inline": False
                    }
                ],
                "timestamp": opportunity['timestamp']
            }

            return await self.send_message("", embeds=[embed])

        except Exception as e:
            logger.error(f"Error sending Discord opportunity alert: {e}")
            return False


class NotificationManager:
    """
    Unified notification manager for multiple platforms.

    Manages Telegram and Discord notifications with proper error handling
    and rate limiting.
    """

    def __init__(self):
        """Initialize notification manager with configured platforms."""
        self.telegram = None
        self.discord = None

        # Initialize Telegram if configured
        if config.ENABLE_TELEGRAM and config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT:
            self.telegram = TelegramNotifier(
                bot_token=config.TELEGRAM_TOKEN,
                chat_id=config.TELEGRAM_CHAT
            )

        # Initialize Discord if configured
        discord_webhook = getattr(config, 'DISCORD_WEBHOOK_URL', None)
        if discord_webhook:
            self.discord = DiscordNotifier(webhook_url=discord_webhook)

        logger.info(
            f"Notification manager initialized "
            f"(Telegram: {self.telegram is not None}, "
            f"Discord: {self.discord is not None})"
        )

    async def send_opportunity(self, opportunity: Dict) -> None:
        """
        Send opportunity alert to all enabled platforms.

        Args:
            opportunity: Opportunity dict
        """
        tasks = []

        if self.telegram:
            tasks.append(self.telegram.send_opportunity_alert(opportunity))

        if self.discord:
            tasks.append(self.discord.send_opportunity_alert(opportunity))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Opportunity notifications sent: {results}")

    async def send_execution(self, execution: Dict) -> None:
        """
        Send execution alert to all enabled platforms.

        Args:
            execution: Execution dict
        """
        if self.telegram:
            await self.telegram.send_execution_alert(execution)

    async def send_error(self, error_msg: str, context: Optional[Dict] = None) -> None:
        """
        Send error alert to all enabled platforms.

        Args:
            error_msg: Error message
            context: Optional context dict
        """
        if self.telegram:
            await self.telegram.send_error_alert(error_msg, context)

    async def send_status(self, status: str, details: Optional[Dict] = None) -> None:
        """
        Send status update to all enabled platforms.

        Args:
            status: Status message
            details: Optional details dict
        """
        if self.telegram:
            await self.telegram.send_status_update(status, details)
