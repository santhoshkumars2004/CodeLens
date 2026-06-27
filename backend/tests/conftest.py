"""
CodeLens Test Fixtures.

Shared pytest fixtures for backend tests.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_repo_url():
    """Sample GitHub repo URL for testing."""
    return "https://github.com/tiangolo/fastapi"


@pytest.fixture
def sample_python_code():
    """Sample Python code for chunking tests."""
    return '''
import os
from typing import List

MAX_SIZE = 100

def hello_world():
    """Say hello."""
    print("Hello, World!")

def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history = []

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        result = a * b
        self.history.append(result)
        return result
'''
