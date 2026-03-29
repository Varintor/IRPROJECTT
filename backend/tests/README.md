# 🧪 Testing Suite - SE481 IR Project

This directory contains unit tests and integration tests for the recipe recommendation system.

## 📁 File Structure

```
testing/
├── unit_test.py         # Unit tests for individual components
├── integration_test.py  # Integration tests for API endpoints
└── README.md           # This file
```

## 🚀 Quick Start

### Prerequisites

Make sure you have the required dependencies installed:
```bash
pip install pytest unittest
```

### Running Tests

#### Option 1: Run Directly with Python

```bash
# Unit Tests
python testing/unit_test.py

# Integration Tests
python testing/integration_test.py

# Both Tests
python testing/unit_test.py && python testing/integration_test.py
```

#### Option 2: Run with Pytest

```bash
# Unit Tests only
pytest testing/unit_test.py -v

# Integration Tests only
pytest testing/integration_test.py -v

# All Tests
pytest testing/ -v
```

## 📋 Test Coverage

### Unit Tests (`unit_test.py`)

Tests individual components in isolation:

- ✅ **User Model** (`TestUserModel`)
  - User creation
  - User serialization (`to_dict()`)
  - Password hashing verification

- ✅ **Folder Model** (`TestFolderModel`)
  - Folder creation
  - Folder serialization

- ✅ **Bookmark Model** (`TestBookmarkModel`)
  - Bookmark creation
  - Bookmark serialization
  - Foreign key relationships

- ✅ **RecipeRating Model** (`TestRecipeRatingModel`)
  - Rating creation
  - Rating validation (1-5 scale)
  - Review text handling

- ✅ **CASCADE DELETE** (`TestCascadeDelete`)
  - Parent-child relationships
  - Referential integrity

- ✅ **Helper Functions** (`TestHelperFunctions`)
  - Duration formatting (ISO 8601 → human-readable)

**Total Unit Tests**: 15+ test cases

### Integration Tests (`integration_test.py`)

Tests how components work together:

- ✅ **Health Endpoints** (`TestHealthEndpoints`)
  - `/api/health` - Server health check
  - `/api/test-db` - Database connection

- ✅ **Authentication** (`TestAuthenticationEndpoints`)
  - `POST /api/register` - User registration
  - `POST /api/login` - User login
  - `GET /api/auth/verify` - JWT token verification

- ✅ **Folder Management** (`TestFolderEndpoints`)
  - `POST /api/folders` - Create folder
  - `GET /api/folders` - List folders
  - `DELETE /api/folders/<id>` - Delete folder

- ✅ **Bookmark Management** (`TestBookmarkEndpoints`)
  - `POST /api/bookmarks` - Add bookmark
  - `GET /api/bookmarks` - List bookmarks
  - `DELETE /api/bookmarks/<id>` - Remove bookmark

- ✅ **Search Functionality** (`TestSearchEndpoints`)
  - `GET /search` - Recipe search with Elasticsearch
  - `POST /api/spellcheck` - Spell correction

- ✅ **Recipe Retrieval** (`TestRecipeEndpoints`)
  - `POST /api/recipes/by-ids` - Get multiple recipes by IDs

- ✅ **ML Recommendations** (`TestMLOperations`)
  - `GET /api/recommendations/ml` - TF-IDF content-based filtering

- ✅ **Performance Tests** (`TestPerformance`)
  - Response time validation
  - Sequential request handling

**Total Integration Tests**: 20+ test cases

## 📊 Expected Output

### Unit Tests

```
test_bookmark_creation ... ok
test_bookmark_to_dict ... ok
test_folder_creation ... ok
test_folder_to_dict ... ok
test_rating_creation ... ok
test_rating_to_dict ... ok
test_rating_validation ... ok
test_user_creation ... ok
test_user_to_dict ... ok
...

======================================================================
UNIT TEST SUMMARY
======================================================================
Tests Run: 15
Successes: 15
Failures: 0
Errors: 0
Skipped: 0
======================================================================
```

### Integration Tests

```
test_health_check ... ok
test_database_connection ... ok
test_user_registration ... ok
test_user_login ... ok
test_create_bookmark ... ok
test_search_endpoint ... ok
...

======================================================================
INTEGRATION TEST SUMMARY
======================================================================
Tests Run: 20
Successes: 18
Failures: 1
Errors: 1
Skipped: 0
======================================================================
```

## 🔍 Troubleshooting

### Common Issues

**1. Import Errors**
```
ModuleNotFoundError: No module named 'models'
```
**Solution**: Make sure you're running tests from the `backend/` directory:
```bash
cd backend
python testing/unit_test.py
```

**2. Database Connection Errors**
```
sqlalchemy.exc.OperationalError: Unable to connect
```
**Solution**: Ensure PostgreSQL is running and `.env` file has correct credentials.

**3. Elasticsearch Connection Errors**
```
ConnectionError: Connection refused
```
**Solution**: Start Elasticsearch service:
```bash
# Windows
elasticsearch.bat

# Linux/Mac
./bin/elasticsearch
```

**4. Integration Test Timeouts**
```
TimeoutError: Search took 15.2s, expected < 5s
```
**Solution**: This is normal if:
- Elasticsearch is indexing
- ML models are loading
- First run after server start

## 📈 Test Coverage Goals

- ✅ **Models**: 100% coverage (User, Folder, Bookmark, RecipeRating)
- ✅ **API Endpoints**: >80% coverage
- ✅ **Business Logic**: >90% coverage
- ✅ **Helper Functions**: 100% coverage

## 🎯 Running Specific Tests

### Run a Single Test Class

```bash
# Unit tests only
python -m pytest testing/unit_test.py::TestUserModel -v

# Integration tests only
python -m pytest testing/integration_test.py::TestSearchEndpoints -v
```

### Run a Single Test Method

```bash
# Specific test method
python -m pytest testing/unit_test.py::TestUserModel::test_user_creation -v
```

## 📝 Adding New Tests

1. **Create a new test class**:
   ```python
   class TestNewFeature(unittest.TestCase):
       def setUp(self):
           # Set up test fixtures
           pass

       def test_new_functionality(self):
           # Your test code here
           self.assertEqual(expected, actual)
   ```

2. **Add to test suite**:
   ```python
   suite.addTests(loader.loadTestsFromTestCase(TestNewFeature))
   ```

3. **Run tests**:
   ```bash
   python testing/unit_test.py
   ```

## 🔗 Related Files

- `backend/models.py` - Database models
- `backend/app.py` - Flask application and API routes
- `backend/elastic_search.py` - Elasticsearch integration
- `backend/api_recommendations.py` - ML recommendation engine

## 📚 Resources

- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html)
- [Pytest Documentation](https://docs.pytest.org/)
- [Flask Testing Guide](https://flask.palletsprojects.com/en/2.3.x/testing/)

---

**Generated**: 2026-03-30
**SE481 Information Retrieval Project**
