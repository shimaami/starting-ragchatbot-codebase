"""Pytest configuration and shared fixtures for backend tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend/ to sys.path so imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

# --- Module-level patches (must happen BEFORE app.py is imported) ---

# Default mock RAGSystem instance shared across the session
_mock_rag_instance = MagicMock()
_mock_rag_instance.query.return_value = ("Test answer", [])  # Empty sources by default
_mock_rag_instance.get_course_analytics.return_value = {
    "total_courses": 2,
    "course_titles": ["Course A", "Course B"],
}
_mock_rag_instance.session_manager.create_session.return_value = "session_test_1"
_mock_rag_instance.session_manager.get_conversation_history.return_value = None

# 1. Patch RAGSystem so `rag_system = RAGSystem(config)` returns our mock
_rag_patcher = patch("rag_system.RAGSystem", return_value=_mock_rag_instance)
_rag_patcher.start()

# 2. Patch StaticFiles so `StaticFiles(directory="../frontend")` doesn't error
_static_patcher = patch("fastapi.staticfiles.StaticFiles")
_mock_static_cls = _static_patcher.start()
_mock_static_cls.return_value = MagicMock()

# Now safe to import app
from app import app as _app  # noqa: E402

import pytest
from fastapi.testclient import TestClient
import app as _app_module


# --- Per-test fixtures ---


@pytest.fixture
def mock_rag():
    """Reset the shared mock RAGSystem to clean defaults before each test."""
    _mock_rag_instance.reset_mock(return_value=True, side_effect=True)
    _mock_rag_instance.query.return_value = ("Test answer", [])
    _mock_rag_instance.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    _mock_rag_instance.session_manager.create_session.return_value = "session_test_1"
    return _mock_rag_instance


@pytest.fixture
def client(mock_rag):
    """TestClient with mock RAGSystem injected into app module."""
    _app_module.rag_system = mock_rag
    return TestClient(_app)


@pytest.fixture
def sample_query_payload():
    """Sample request payload for /api/query."""
    return {"query": "What is covered in Lesson 1?"}


@pytest.fixture
def sample_courses_response():
    """Sample expected response structure for /api/courses."""
    return {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
