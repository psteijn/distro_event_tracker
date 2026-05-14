import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import main
from main import ask
from tests.utils_discord_mocks import DummyCtx as MockContext

@pytest.mark.asyncio
async def test_ask_command_success():
    ctx = MockContext()
    
    # Create an async context manager mock
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock()
    mock_manager.__aexit__ = AsyncMock()
    ctx.typing = MagicMock(return_value=mock_manager)
    
    # Mock the subprocess execution
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Gemini says hello!", b"")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process
        
        await ask(ctx, question="What is your name?")
        
        # Verify it called the right command
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        assert "gemini.cmd" in args
        assert "What is your name?" in args
        assert "plan" in args
        
        # Verify it sent the response
        assert len(ctx.sent) == 1
        assert ctx.sent[0]["msg"] == "Gemini says hello!"

@pytest.mark.asyncio
async def test_ask_command_empty_question():
    ctx = MockContext()
    await ask(ctx, question="   ")
    assert len(ctx.sent) == 1
    assert ctx.sent[0]["msg"] == "❌ Please provide a question!"

@pytest.mark.asyncio
async def test_ask_command_error():
    ctx = MockContext()
    
    # Create an async context manager mock
    mock_manager = AsyncMock()
    mock_manager.__aenter__ = AsyncMock()
    mock_manager.__aexit__ = AsyncMock()
    ctx.typing = MagicMock(return_value=mock_manager)
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Something went wrong")
        mock_process.returncode = 1
        mock_exec.return_value = mock_process
        
        await ask(ctx, question="Fail me")
        
        assert len(ctx.sent) == 1
        assert ctx.sent[0]["msg"] == "❌ Sorry, I encountered an error while processing your question."
