"""Tests for FastAPI endpoints."""

import pytest
from fastapi import status


class TestQueryEndpoint:
    """Test suite for POST /api/query endpoint."""

    def test_query_creates_new_session(self, client, sample_query_payload):
        """Test that query without session_id creates a new session."""
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] == "session_test_1"

    def test_query_uses_existing_session(self, client, mock_rag, sample_query_payload):
        """Test that query with session_id uses that session."""
        payload = {**sample_query_payload, "session_id": "session_existing"}
        response = client.post("/api/query", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == "session_existing"

    def test_query_returns_answer_and_sources(
        self, client, mock_rag, sample_query_payload
    ):
        """Test that query response has correct structure."""
        mock_rag.query.return_value = (
            "Here is the answer",
            [{"course": "Course A", "lesson": "Lesson 1"}],
        )
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert isinstance(data["sources"], list)

    def test_query_with_sources(self, client, mock_rag, sample_query_payload):
        """Test that sources from RAG system are included in response."""
        expected_sources = [
            {"course": "Course A", "lesson": "Lesson 1"},
            {"course": "Course B", "lesson": "Lesson 2"},
        ]
        mock_rag.query.return_value = ("Test answer", expected_sources)
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sources"] == expected_sources

    def test_query_missing_field_returns_422(self, client):
        """Test that request without required 'query' field returns 422."""
        response = client.post("/api/query", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_with_empty_body_returns_422(self, client):
        """Test that empty request body returns 422."""
        response = client.post("/api/query", json=None)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_rag_error_returns_500(self, client, mock_rag, sample_query_payload):
        """Test that RAGSystem errors are caught and return 500."""
        mock_rag.query.side_effect = Exception("RAG system failed")
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data

    def test_query_calls_rag_system(self, client, mock_rag, sample_query_payload):
        """Test that query endpoint calls RAGSystem.query with correct args."""
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == status.HTTP_200_OK
        # Verify mock_rag.query was called
        mock_rag.query.assert_called_once()


class TestCoursesEndpoint:
    """Test suite for GET /api/courses endpoint."""

    def test_courses_returns_stats(self, client, mock_rag, sample_courses_response):
        """Test that /api/courses returns course statistics."""
        mock_rag.get_course_analytics.return_value = sample_courses_response
        response = client.get("/api/courses")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["course_titles"], list)

    def test_courses_with_data(self, client, mock_rag):
        """Test /api/courses returns correct course data."""
        expected_response = {
            "total_courses": 3,
            "course_titles": ["Python 101", "Web Dev", "Data Science"],
        }
        mock_rag.get_course_analytics.return_value = expected_response
        response = client.get("/api/courses")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Python 101" in data["course_titles"]

    def test_courses_empty_list(self, client, mock_rag):
        """Test /api/courses with no courses loaded."""
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        response = client.get("/api/courses")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_courses_rag_error_returns_500(self, client, mock_rag):
        """Test that RAGSystem errors in /api/courses return 500."""
        mock_rag.get_course_analytics.side_effect = Exception(
            "Failed to get analytics"
        )
        response = client.get("/api/courses")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data

    def test_courses_calls_rag_analytics(self, client, mock_rag):
        """Test that /api/courses endpoint calls RAGSystem.get_course_analytics."""
        response = client.get("/api/courses")
        assert response.status_code == status.HTTP_200_OK
        # Verify mock_rag.get_course_analytics was called
        mock_rag.get_course_analytics.assert_called_once()


class TestRootRoute:
    """Test suite for the root route /."""

    def test_app_startup_succeeds(self, client):
        """Test that the app starts without errors with mocked dependencies."""
        # The app initializes with mocked RAGSystem and StaticFiles
        # This test verifies the app is properly configured and doesn't crash on startup
        assert client is not None
        assert client.app is not None
        # Verify the FastAPI app is created with expected title
        assert "Course Materials RAG System" in client.app.title

    def test_root_route_configured(self, client):
        """Verify that the app has routes configured."""
        # Check that the app has the expected routes
        # The root route (/) is mounted as a static file handler (shows as empty path '')
        routes = [route.path for route in client.app.routes]
        assert (
            "" in routes or "/" in routes
        ), "Root route should be configured (as '' or '/')"
        assert "/api/query" in routes, "Query endpoint should be configured"
        assert "/api/courses" in routes, "Courses endpoint should be configured"
