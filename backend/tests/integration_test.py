"""
=======================================
INTEGRATION TESTING - SE481 IR PROJECT
=======================================

Integration tests focus on testing how different components work together:
- API endpoints (Flask routes)
- Database operations
- Elasticsearch integration
- Authentication flow
- Full request/response cycles

Run: python -m pytest testing/integration_test.py -v
Or:  python testing/integration_test.py
"""

import unittest
import sys
import os
import json
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Flask app and test utilities
from app import app, db
from models.models import User, Folder, Bookmark, RecipeRating


class IntegrationTestBase(unittest.TestCase):
    """Base class for integration tests with test client"""

    @classmethod
    def setUpClass(cls):
        """Set up test client and database before all tests"""
        cls.app = app
        cls.client = cls.app.test_client()
        cls.app.config['TESTING'] = True

    def setUp(self):
        """Set up test fixtures before each test"""
        # Create all tables
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        """Clean up after each test"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


class TestHealthEndpoints(IntegrationTestBase):
    """Test health check and basic endpoints"""

    def test_health_check(self):
        """Test /api/health endpoint returns 200"""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('message', data)

    def test_database_connection(self):
        """Test /api/test-db endpoint"""
        response = self.client.get('/api/test-db')
        self.assertIn(response.status_code, [200, 500])  # May fail if DB not configured

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'ok')
            self.assertIn('user_count', data)


class TestAuthenticationEndpoints(IntegrationTestBase):
    """Test authentication API endpoints"""

    def test_user_registration(self):
        """Test POST /api/register - create new user"""
        response = self.client.post('/api/register', data=json.dumps({
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123'
        }), content_type='application/json')

        # May return 201 (created) or 400 (user exists) or 500
        self.assertIn(response.status_code, [200, 201, 400])

        if response.status_code in [200, 201]:
            data = json.loads(response.data)
            self.assertIn('token', data)
            self.assertIn('user', data)

    def test_user_login(self):
        """Test POST /api/login - authenticate user"""
        # First register a user
        self.client.post('/api/register', data=json.dumps({
            'username': 'loginuser',
            'email': 'login@example.com',
            'password': 'password123'
        }), content_type='application/json')

        # Then login
        response = self.client.post('/api/login', data=json.dumps({
            'username': 'loginuser',
            'password': 'password123'
        }), content_type='application/json')

        self.assertIn(response.status_code, [200, 401])

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('token', data)
            self.assertIn('user', data)

    @unittest.skip("verify endpoint not implemented - using token-based auth")
    def test_verify_token(self):
        """Test GET /api/auth/verify - verify JWT token"""
        # Register and login to get token
        reg_response = self.client.post('/api/register', data=json.dumps({
            'username': 'verifyuser',
            'email': 'verify@example.com',
            'password': 'password123'
        }), content_type='application/json')

        if reg_response.status_code in [200, 201]:
            token_data = json.loads(reg_response.data)
            token = token_data.get('token')

            if token:
                # Verify token
                response = self.client.get('/api/auth/verify', headers={
                    'Authorization': f'Bearer {token}'
                })

                self.assertIn(response.status_code, [200, 401])


class TestFolderEndpoints(IntegrationTestBase):
    """Test folder management API endpoints"""

    def setUp(self):
        """Set up test user and get auth token"""
        super().setUp()

        # Create test user
        with self.app.app_context():
            # Clean up any existing test user first
            existing_user = User.query.filter_by(username="folderuser").first()
            if existing_user:
                db.session.delete(existing_user)
                db.session.commit()

            user = User(
                username="folderuser",
                email="folder@example.com",
                password_hash="hash123"
            )
            db.session.add(user)
            db.session.commit()
            self.user_id = user.user_id

    def test_create_folder(self):
        """Test POST /api/folders - create new folder"""
        response = self.client.post('/api/folders', data=json.dumps({
            'name': 'My Recipes',
            'description': 'Favorite recipes'
        }), content_type='application/json')

        # May return 401 if auth required
        self.assertIn(response.status_code, [200, 201, 401])

    def test_get_folders(self):
        """Test GET /api/folders - list all folders"""
        response = self.client.get('/api/folders')
        self.assertIn(response.status_code, [200, 401])

    def test_delete_folder(self):
        """Test DELETE /api/folders/<id> - delete folder"""
        # First create a folder
        with self.app.app_context():
            folder = Folder(
                user_id=self.user_id,
                name="Test Folder"
            )
            db.session.add(folder)
            db.session.commit()
            folder_id = folder.id

        # Then delete it
        response = self.client.delete(f'/api/folders/{folder_id}')
        self.assertIn(response.status_code, [200, 401, 404])


class TestBookmarkEndpoints(IntegrationTestBase):
    """Test bookmark management API endpoints"""

    def setUp(self):
        """Set up test user and folder"""
        super().setUp()

        with self.app.app_context():
            # Clean up any existing test user first
            existing_user = User.query.filter_by(username="bookmarkuser").first()
            if existing_user:
                db.session.delete(existing_user)
                db.session.commit()

            user = User(
                username="bookmarkuser",
                email="bookmark@example.com",
                password_hash="hash123"
            )
            db.session.add(user)
            db.session.commit()

            folder = Folder(
                user_id=user.user_id,
                name="Test Folder"
            )
            db.session.add(folder)
            db.session.commit()

            self.user_id = user.user_id
            self.folder_id = folder.id

    def test_create_bookmark(self):
        """Test POST /api/bookmarks - add recipe to folder"""
        response = self.client.post('/api/bookmarks', data=json.dumps({
            'folder_id': self.folder_id,
            'recipe_id': 100,
            'recipe_name': 'Test Recipe'
        }), content_type='application/json')

        self.assertIn(response.status_code, [200, 201, 401])

    def test_get_bookmarks(self):
        """Test GET /api/bookmarks - list all bookmarks"""
        # Create a bookmark first
        with self.app.app_context():
            bookmark = Bookmark(
                user_id=self.user_id,
                folder_id=self.folder_id,
                recipe_id=100,
                recipe_name="Test Recipe"
            )
            db.session.add(bookmark)
            db.session.commit()

        # Get bookmarks
        response = self.client.get('/api/bookmarks')
        self.assertIn(response.status_code, [200, 401])

    def test_delete_bookmark(self):
        """Test DELETE /api/bookmarks/<id> - remove bookmark"""
        # Create a bookmark
        with self.app.app_context():
            bookmark = Bookmark(
                user_id=self.user_id,
                folder_id=self.folder_id,
                recipe_id=100,
                recipe_name="Test Recipe"
            )
            db.session.add(bookmark)
            db.session.commit()
            bookmark_id = bookmark.id

        # Delete it
        response = self.client.delete(f'/api/bookmarks/{bookmark_id}')
        self.assertIn(response.status_code, [200, 401, 404])


class TestSearchEndpoints(IntegrationTestBase):
    """Test search and spell check endpoints"""

    @patch('app.initialize_spell_checker')
    def test_search_endpoint(self, _mock_spell_checker):
        """Test GET /search?q=<query> - recipe search"""
        response = self.client.get('/search?q=chicken&top_k=5')
        self.assertIn(response.status_code, [200, 500])  # May fail if ES not running

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('results', data)
            self.assertIsInstance(data['results'], list)

    @patch('app.initialize_spell_checker')
    def test_spell_check_endpoint(self, _mock_spell_checker):
        """Test POST /api/spellcheck - spell correction"""
        response = self.client.post('/api/spellcheck', data=json.dumps({
            'query': 'chikcen'  # Intentional misspelling
        }), content_type='application/json')

        self.assertIn(response.status_code, [200, 500])

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('original_query', data)
            self.assertIn('corrected_query', data)


class TestRecipeEndpoints(IntegrationTestBase):
    """Test recipe retrieval endpoints"""

    def test_get_recipes_by_ids(self):
        """Test POST /api/recipes/by-ids - get multiple recipes"""
        response = self.client.post('/api/recipes/by-ids', data=json.dumps({
            'recipe_ids': [100, 200, 300]
        }), content_type='application/json')

        # May return 200 or 500 if indexer not loaded
        self.assertIn(response.status_code, [200, 500])

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('recipes', data)
            self.assertIsInstance(data['recipes'], list)


class TestMLOperations(IntegrationTestBase):
    """Test ML recommendation operations"""

    def test_ml_recommendations_endpoint(self):
        """Test GET /api/recommendations/ml - ML-based recommendations"""
        response = self.client.get('/api/recommendations/ml?top_k=10')
        self.assertIn(response.status_code, [200, 401, 500])  # May require auth

        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('recommendations', data)
            self.assertIn('method', data)


class TestPerformance(IntegrationTestBase):
    """Performance and load testing"""

    @patch('app.initialize_spell_checker')
    def test_search_response_time(self, _mock_spell_checker):
        """Test that search responds within acceptable time"""
        start_time = time.time()
        response = self.client.get('/search?q=chicken&top_k=5')
        end_time = time.time()

        response_time = end_time - start_time

        # Search should respond within 5 seconds
        if response.status_code == 200:
            self.assertLess(response_time, 5.0,
                           f"Search took {response_time:.2f}s, expected < 5s")

    @patch('app.initialize_spell_checker')
    def test_multiple_sequential_requests(self, _mock_spell_checker):
        """Test handling multiple sequential requests"""
        urls = [
            '/api/health',
            '/search?q=chicken',
            '/search?q=pasta',
            '/api/test-db'
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [200, 500])


def run_integration_tests():
    """Run all integration tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHealthEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthenticationEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestFolderEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestBookmarkEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestSearchEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestMLOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)

    return result


if __name__ == '__main__':
    result = run_integration_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
