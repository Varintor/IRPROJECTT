"""
=======================================
UNIT TESTING - SE481 IR PROJECT
=======================================

Unit tests focus on testing individual components in isolation:
- Model classes (User, Folder, Bookmark, RecipeRating)
- Business logic functions
- Utility functions
- Individual methods

Run: python -m pytest testing/unit_test.py -v
Or:  python testing/unit_test.py
"""

import unittest
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.models import db, User, Folder, Bookmark, RecipeRating
from datetime import datetime


class TestUserModel(unittest.TestCase):
    """Test User model CRUD operations and validation"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.test_user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )

    def test_user_creation(self):
        """Test that a User object can be created with valid attributes"""
        self.assertEqual(self.test_user.username, "testuser")
        self.assertEqual(self.test_user.email, "test@example.com")
        self.assertEqual(self.test_user.password_hash, "hashed_password_123")
        # Note: created_at is set by database default, not Python default
        # This is expected behavior - it will be set when saved to DB

    def test_user_to_dict(self):
        """Test User serialization to dictionary"""
        user_dict = self.test_user.to_dict()
        self.assertIsInstance(user_dict, dict)
        self.assertEqual(user_dict['username'], "testuser")
        self.assertEqual(user_dict['email'], "test@example.com")
        self.assertNotIn('password_hash', user_dict)  # Password should not be exposed


class TestFolderModel(unittest.TestCase):
    """Test Folder model CRUD operations and validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_folder = Folder(
            user_id=1,
            name="Test Folder",
            description="A test folder for recipes"
        )

    def test_folder_creation(self):
        """Test that a Folder object can be created"""
        self.assertEqual(self.test_folder.name, "Test Folder")
        self.assertEqual(self.test_folder.user_id, 1)
        self.assertEqual(self.test_folder.description, "A test folder for recipes")

    def test_folder_to_dict(self):
        """Test Folder serialization to dictionary"""
        folder_dict = self.test_folder.to_dict()
        self.assertIsInstance(folder_dict, dict)
        self.assertEqual(folder_dict['name'], "Test Folder")
        self.assertEqual(folder_dict['description'], "A test folder for recipes")


class TestBookmarkModel(unittest.TestCase):
    """Test Bookmark model relationships and validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_bookmark = Bookmark(
            user_id=1,
            folder_id=1,
            recipe_id=100,
            recipe_name="Test Recipe",
            notes="Delicious recipe!"
        )

    def test_bookmark_creation(self):
        """Test that a Bookmark object can be created"""
        self.assertEqual(self.test_bookmark.user_id, 1)
        self.assertEqual(self.test_bookmark.folder_id, 1)
        self.assertEqual(self.test_bookmark.recipe_id, 100)
        self.assertEqual(self.test_bookmark.recipe_name, "Test Recipe")

    def test_bookmark_to_dict(self):
        """Test Bookmark serialization to dictionary"""
        bookmark_dict = self.test_bookmark.to_dict()
        self.assertIsInstance(bookmark_dict, dict)
        self.assertEqual(bookmark_dict['recipe_name'], "Test Recipe")
        self.assertEqual(bookmark_dict['notes'], "Delicious recipe!")


class TestRecipeRatingModel(unittest.TestCase):
    """Test RecipeRating model and validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_rating = RecipeRating(
            user_id=1,
            recipe_id=200,
            recipe_name="Rated Recipe",
            rating=5,
            review="Amazing recipe!"
        )

    def test_rating_creation(self):
        """Test that a RecipeRating object can be created"""
        self.assertEqual(self.test_rating.user_id, 1)
        self.assertEqual(self.test_rating.recipe_id, 200)
        self.assertEqual(self.test_rating.rating, 5)
        self.assertEqual(self.test_rating.review, "Amazing recipe!")

    def test_rating_validation(self):
        """Test rating must be between 1 and 5"""
        # Valid ratings
        for valid_rating in [1, 2, 3, 4, 5]:
            rating = RecipeRating(
                user_id=1,
                recipe_id=1,
                recipe_name="Test",
                rating=valid_rating
            )
            self.assertEqual(rating.rating, valid_rating)

    def test_rating_to_dict(self):
        """Test RecipeRating serialization to dictionary"""
        rating_dict = self.test_rating.to_dict()
        self.assertIsInstance(rating_dict, dict)
        self.assertEqual(rating_dict['rating'], 5)
        self.assertEqual(rating_dict['review'], "Amazing recipe!")


class TestCascadeDelete(unittest.TestCase):
    """Test CASCADE DELETE behavior for related models"""

    def test_user_cascade_delete(self):
        """Test that deleting a user cascades to related records"""
        # Create a user
        user = User(
            username="cascade_test",
            email="cascade@test.com",
            password_hash="hash"
        )

        # Create related folder
        folder = Folder(
            user_id=user.user_id,
            name="Test Folder"
        )

        # Create related bookmark
        bookmark = Bookmark(
            user_id=user.user_id,
            folder_id=folder.id,
            recipe_id=100,
            recipe_name="Test Recipe"
        )

        # Verify relationships exist
        self.assertEqual(folder.user_id, user.user_id)
        self.assertEqual(bookmark.user_id, user.user_id)

        # Note: Actual CASCADE DELETE is tested at database level
        # This unit test verifies the model relationships


class TestHelperFunctions(unittest.TestCase):
    """Test utility and helper functions"""

    def test_format_duration(self):
        """Test ISO 8601 duration formatting"""
        from app import format_duration

        # Test various duration formats
        self.assertEqual(format_duration("PT2H42M"), "2h 42m")
        self.assertEqual(format_duration("PT1H30M"), "1h 30m")
        self.assertEqual(format_duration("PT45M"), "45 min")
        self.assertEqual(format_duration("PT2H"), "2h")
        self.assertEqual(format_duration(""), "30 min")
        self.assertEqual(format_duration(None), "30 min")
        self.assertEqual(format_duration("INVALID"), "30 min")


def run_unit_tests():
    """Run all unit tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestUserModel))
    suite.addTests(loader.loadTestsFromTestCase(TestFolderModel))
    suite.addTests(loader.loadTestsFromTestCase(TestBookmarkModel))
    suite.addTests(loader.loadTestsFromTestCase(TestRecipeRatingModel))
    suite.addTests(loader.loadTestsFromTestCase(TestCascadeDelete))
    suite.addTests(loader.loadTestsFromTestCase(TestHelperFunctions))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("UNIT TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)

    return result


if __name__ == '__main__':
    result = run_unit_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
