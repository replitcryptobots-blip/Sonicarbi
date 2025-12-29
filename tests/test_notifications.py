"""
Unit tests for Telegram and Discord notifications.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from utils.notifications import TelegramNotifier, DiscordNotifier, NotificationManager
from datetime import datetime


@pytest.fixture
def telegram_notifier():
    """Create a TelegramNotifier instance for testing."""
    return TelegramNotifier(
        bot_token='123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
        chat_id='123456789'
    )


@pytest.fixture
def discord_notifier():
    """Create a DiscordNotifier instance for testing."""
    return DiscordNotifier(
        webhook_url='https://discord.com/api/webhooks/123456/abcdef'
    )


@pytest.fixture
def sample_opportunity():
    """Sample arbitrage opportunity for testing."""
    return {
        'timestamp': '2025-12-29T10:30:00',
        'token_in': 'WETH',
        'token_out': 'USDC',
        'buy_dex': 'SyncSwap',
        'sell_dex': 'Zebra',
        'buy_price': 3500.123456,
        'sell_price': 3520.654321,
        'profit_pct': 0.583,
        'profit_usd': 20.43,
        'gas_cost_usd': 0.05,
        'gas_estimate': 350000,
        'amount': 1.0
    }


@pytest.fixture
def sample_execution():
    """Sample execution for testing."""
    return {
        'timestamp': '2025-12-29T10:35:00',
        'token_in': 'WETH',
        'token_out': 'USDC',
        'buy_dex': 'SyncSwap',
        'sell_dex': 'Zebra',
        'status': 'success',
        'tx_hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        'actual_profit_pct': 0.58,
        'actual_profit_usd': 20.30
    }


class TestTelegramNotifier:
    """Test TelegramNotifier functionality."""

    def test_initialization_enabled(self, telegram_notifier):
        """Test notifier initialization when enabled."""
        assert telegram_notifier.enabled is True
        assert telegram_notifier.bot_token is not None
        assert telegram_notifier.chat_id is not None

    def test_initialization_disabled(self):
        """Test notifier initialization when disabled."""
        notifier = TelegramNotifier(bot_token='', chat_id='')
        assert notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_message_disabled(self):
        """Test that disabled notifier doesn't send messages."""
        notifier = TelegramNotifier(bot_token='', chat_id='')
        result = await notifier.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, telegram_notifier):
        """Test successful message sending."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response

            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post

            result = await telegram_notifier.send_message("Test message")

            assert result is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, telegram_notifier):
        """Test message sending with API error."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value='Bad Request')
            mock_response.__aenter__.return_value = mock_response

            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post

            result = await telegram_notifier.send_message("Test message")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, telegram_notifier):
        """Test message sending with timeout."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.side_effect = asyncio.TimeoutError()

            result = await telegram_notifier.send_message("Test message")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_opportunity_alert(self, telegram_notifier, sample_opportunity):
        """Test sending opportunity alert."""
        with patch.object(telegram_notifier, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await telegram_notifier.send_opportunity_alert(sample_opportunity)

            assert result is True
            mock_send.assert_called_once()

            # Check that message contains key information
            call_args = mock_send.call_args[0][0]
            assert 'WETH' in call_args
            assert 'USDC' in call_args
            assert 'SyncSwap' in call_args
            assert 'Zebra' in call_args
            assert '0.583%' in call_args or '0.583' in call_args

    @pytest.mark.asyncio
    async def test_send_execution_alert(self, telegram_notifier, sample_execution):
        """Test sending execution alert."""
        with patch.object(telegram_notifier, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await telegram_notifier.send_execution_alert(sample_execution)

            assert result is True
            mock_send.assert_called_once()

            # Check message contains execution info
            call_args = mock_send.call_args[0][0]
            assert 'success' in call_args.lower()
            assert sample_execution['tx_hash'] in call_args

    @pytest.mark.asyncio
    async def test_send_error_alert(self, telegram_notifier):
        """Test sending error alert."""
        with patch.object(telegram_notifier, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            context = {'error_code': 500, 'details': 'Internal error'}
            result = await telegram_notifier.send_error_alert("Test error", context)

            assert result is True
            mock_send.assert_called_once()

            call_args = mock_send.call_args[0][0]
            assert 'Test error' in call_args
            assert 'error_code' in call_args

    @pytest.mark.asyncio
    async def test_send_status_update(self, telegram_notifier):
        """Test sending status update."""
        with patch.object(telegram_notifier, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            details = {'uptime': '24h', 'scans': 1000}
            result = await telegram_notifier.send_status_update("System running", details)

            assert result is True
            mock_send.assert_called_once()

            call_args = mock_send.call_args[0][0]
            assert 'System running' in call_args


class TestDiscordNotifier:
    """Test DiscordNotifier functionality."""

    def test_initialization_enabled(self, discord_notifier):
        """Test notifier initialization when enabled."""
        assert discord_notifier.enabled is True
        assert discord_notifier.webhook_url is not None

    def test_initialization_disabled(self):
        """Test notifier initialization when disabled."""
        notifier = DiscordNotifier(webhook_url=None)
        assert notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_message_disabled(self):
        """Test that disabled notifier doesn't send messages."""
        notifier = DiscordNotifier(webhook_url=None)
        result = await notifier.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, discord_notifier):
        """Test successful message sending."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response

            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post

            result = await discord_notifier.send_message("Test message")

            assert result is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_with_embeds(self, discord_notifier):
        """Test message sending with embeds."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response

            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post

            embeds = [{'title': 'Test', 'description': 'Test embed'}]
            result = await discord_notifier.send_message("", embeds=embeds)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_opportunity_alert(self, discord_notifier, sample_opportunity):
        """Test sending opportunity alert."""
        with patch.object(discord_notifier, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await discord_notifier.send_opportunity_alert(sample_opportunity)

            assert result is True
            mock_send.assert_called_once()

            # Check that embeds were sent
            call_args = mock_send.call_args
            assert 'embeds' in call_args[1]
            embeds = call_args[1]['embeds']
            assert len(embeds) > 0
            assert embeds[0]['title'] == '🎯 Arbitrage Opportunity Found'


class TestNotificationManager:
    """Test NotificationManager functionality."""

    def test_initialization_no_platforms(self):
        """Test initialization with no platforms configured."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = False
            mock_config.TELEGRAM_TOKEN = None
            mock_config.TELEGRAM_CHAT = None

            manager = NotificationManager()

            assert manager.telegram is None
            assert manager.discord is None

    def test_initialization_with_telegram(self):
        """Test initialization with Telegram configured."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = True
            mock_config.TELEGRAM_TOKEN = 'test_token'
            mock_config.TELEGRAM_CHAT = 'test_chat'

            manager = NotificationManager()

            assert manager.telegram is not None

    @pytest.mark.asyncio
    async def test_send_opportunity_both_platforms(self, sample_opportunity):
        """Test sending opportunity to multiple platforms."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = True
            mock_config.TELEGRAM_TOKEN = 'test_token'
            mock_config.TELEGRAM_CHAT = 'test_chat'

            manager = NotificationManager()

            # Mock both notifiers
            manager.telegram = Mock()
            manager.telegram.send_opportunity_alert = AsyncMock(return_value=True)
            manager.discord = Mock()
            manager.discord.send_opportunity_alert = AsyncMock(return_value=True)

            await manager.send_opportunity(sample_opportunity)

            manager.telegram.send_opportunity_alert.assert_called_once_with(sample_opportunity)
            manager.discord.send_opportunity_alert.assert_called_once_with(sample_opportunity)

    @pytest.mark.asyncio
    async def test_send_execution(self, sample_execution):
        """Test sending execution alert."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = True
            mock_config.TELEGRAM_TOKEN = 'test_token'
            mock_config.TELEGRAM_CHAT = 'test_chat'

            manager = NotificationManager()
            manager.telegram = Mock()
            manager.telegram.send_execution_alert = AsyncMock(return_value=True)

            await manager.send_execution(sample_execution)

            manager.telegram.send_execution_alert.assert_called_once_with(sample_execution)

    @pytest.mark.asyncio
    async def test_send_error(self):
        """Test sending error alert."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = True
            mock_config.TELEGRAM_TOKEN = 'test_token'
            mock_config.TELEGRAM_CHAT = 'test_chat'

            manager = NotificationManager()
            manager.telegram = Mock()
            manager.telegram.send_error_alert = AsyncMock(return_value=True)

            await manager.send_error("Test error", {'key': 'value'})

            manager.telegram.send_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_status(self):
        """Test sending status update."""
        with patch('utils.notifications.config') as mock_config:
            mock_config.ENABLE_TELEGRAM = True
            mock_config.TELEGRAM_TOKEN = 'test_token'
            mock_config.TELEGRAM_CHAT = 'test_chat'

            manager = NotificationManager()
            manager.telegram = Mock()
            manager.telegram.send_status_update = AsyncMock(return_value=True)

            await manager.send_status("Status message", {'detail': 'value'})

            manager.telegram.send_status_update.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
