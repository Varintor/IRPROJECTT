"""
Database initialization and seeding script
Uses actual recipes from cleaned_ready_for_es.pkl
Run: python init_db.py --seed
"""
import sys
import random
from app import app, db
from models import User, Folder, Bookmark, RecipeRating, SearchHistory
from indexer_pkl import IndexerFromPKL

# Set UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def init_database():
    """Initialize database with all tables"""
    print("=" * 60)
    print("🗄️  Initializing Database...")
    print("=" * 60)

    with app.app_context():
        # Drop all tables (WARNING: This deletes all data!)
        print("\n📦 Dropping existing tables...")
        db.drop_all()
        print("✅ Tables dropped")

        # Create all tables
        print("\n📦 Creating tables...")
        db.create_all()
        print("✅ Tables created")

        # Show created tables
        print("\n📋 Created tables:")
        inspector = db.inspect(db.engine)
        for table_name in inspector.get_table_names():
            print(f"   - {table_name}")

        print("\n" + "=" * 60)
        print("✅ Database initialized successfully!")
        print("=" * 60)

def seed_test_data():
    """Seed database with test data using actual recipes from dataset"""
    print("\n" + "=" * 60)
    print("🌱 Seeding Test Data from Dataset...")
    print("=" * 60)

    # Load recipes from dataset
    print("\n📚 Loading recipes from dataset...")
    indexer = IndexerFromPKL()
    recipes_df = indexer.documents
    print(f"✅ Loaded {len(recipes_df)} recipes")

    with app.app_context():
        # Create test users
        print("\n👤 Creating test users...")
        from werkzeug.security import generate_password_hash

        users_to_create = [
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123"
            },
            {
                "username": "recipe_lover",
                "email": "foodie@example.com",
                "password": "foodie123"
            },
            {
                "username": "chef_boy",
                "email": "chef@example.com",
                "password": "chef123"
            }
        ]

        created_users = []
        for user_data in users_to_create:
            # Check if user exists
            existing = User.query.filter_by(username=user_data['username']).first()
            if existing:
                print(f"   ⚠️  User {user_data['username']} already exists, skipping...")
                created_users.append(existing)
                continue

            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=generate_password_hash(user_data['password'])
            )
            db.session.add(user)
            db.session.flush()  # Flush to get the ID
            created_users.append(user)
            print(f"   ✅ Created user: {user.username} (ID: {user.user_id})")

        test_user = created_users[0]

        # Create folders for each user
        print("\n📁 Creating folders...")
        folder_templates = [
            {"name": "Favorites", "description": "My all-time favorite recipes"},
            {"name": "To Try", "description": "Recipes I want to try soon"},
            {"name": "Quick Meals", "description": "Fast and easy recipes"},
            {"name": "Healthy Options", "description": "Nutritious choices"},
        ]

        created_folders = []
        for user in created_users:
            for template in folder_templates:
                # Check if folder exists
                existing = Folder.query.filter_by(user_id=user.user_id, name=template['name']).first()
                if not existing:
                    folder = Folder(
                        name=template['name'],
                        description=template['description'],
                        user_id=user.user_id
                    )
                    db.session.add(folder)
                    db.session.flush()
                    created_folders.append(folder)
            print(f"   ✅ Created {len(folder_templates)} folders for {user.username}")

        # Create bookmarks using actual recipes from dataset
        print("\n🔖 Creating bookmarks from dataset...")

        # Sample diverse recipe IDs from dataset
        sample_recipe_ids = recipes_df['recipe_id'].sample(n=min(20, len(recipes_df)), random_state=42).tolist()

        bookmark_count = 0
        for user in created_users[:2]:  # Create bookmarks for first 2 users
            # Get user's folders
            user_folders = Folder.query.filter_by(user_id=user.user_id).all()

            if len(user_folders) > 0:
                # Assign recipes to folders
                for i, recipe_id in enumerate(sample_recipe_ids[:10]):
                    folder = user_folders[i % len(user_folders)]

                    # Get recipe details
                    recipe_row = recipes_df[recipes_df['recipe_id'] == recipe_id].iloc[0]

                    # Check if bookmark already exists
                    existing = Bookmark.query.filter_by(
                        user_id=user.user_id,
                        folder_id=folder.id,
                        recipe_id=int(recipe_id)
                    ).first()

                    if not existing:
                        bookmark = Bookmark(
                            user_id=user.user_id,
                            folder_id=folder.id,
                            recipe_id=int(recipe_id),
                            recipe_name=recipe_row['name'][:255]  # Limit length
                        )
                        db.session.add(bookmark)
                        bookmark_count += 1

        db.session.commit()
        print(f"   ✅ Created {bookmark_count} bookmarks from dataset")

        # Create ratings using actual recipes
        print("\n⭐ Creating ratings from dataset...")

        rating_count = 0
        for user in created_users[:2]:
            # Sample different recipes for ratings
            rating_recipe_ids = recipes_df['recipe_id'].sample(n=min(15, len(recipes_df)), random_state=43).tolist()

            for recipe_id in rating_recipe_ids:
                recipe_row = recipes_df[recipes_df['recipe_id'] == recipe_id].iloc[0]

                # Check if rating already exists
                existing = RecipeRating.query.filter_by(
                    user_id=user.user_id,
                    recipe_id=int(recipe_id)
                ).first()

                if not existing:
                    rating = RecipeRating(
                        user_id=user.user_id,
                        recipe_id=int(recipe_id),
                        recipe_name=recipe_row['name'][:255],
                        rating=random.randint(3, 5),
                        review=random.choice([
                            "Amazing recipe!",
                            "Pretty good, will make again.",
                            "Family loved it!",
                            "Easy to follow.",
                            "Delicious!"
                        ])
                    )
                    db.session.add(rating)
                    rating_count += 1

        db.session.commit()
        print(f"   ✅ Created {rating_count} ratings from dataset")

        # Create search history
        print("\n🔍 Creating search history...")

        sample_queries = [
            "chicken curry",
            "spaghetti bolognese",
            "chocolate cake",
            "beef stir fry",
            "salad"
        ]

        history_count = 0
        for user in created_users[:2]:
            for query in sample_queries:
                # Simulate search results
                results_count = random.randint(10, 50)

                search_entry = SearchHistory(
                    user_id=user.user_id,
                    query=query,
                    results_count=results_count
                )
                db.session.add(search_entry)
                history_count += 1

        db.session.commit()
        print(f"   ✅ Created {history_count} search history entries")

        print("\n" + "=" * 60)
        print("✅ Test data seeded successfully!")
        print("=" * 60)

        print("\n📝 Test Login Credentials:")
        for user in created_users:
            print(f"   Username: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Password: testpass123 / foodie123 / chef123")

        print("\n📊 Statistics:")
        print(f"   Users: {len(created_users)}")
        print(f"   Folders: {len(created_folders)}")
        print(f"   Bookmarks: {bookmark_count}")
        print(f"   Ratings: {rating_count}")
        print(f"   Search History: {history_count}")
        print("=" * 60)

def show_database_stats():
    """Show current database statistics"""
    print("\n" + "=" * 60)
    print("📊 Database Statistics")
    print("=" * 60)

    with app.app_context():
        users = User.query.all()
        folders = Folder.query.all()
        bookmarks = Bookmark.query.all()
        ratings = RecipeRating.query.all()
        history = SearchHistory.query.all()

        print(f"\n👥 Users: {len(users)}")
        for user in users:
            print(f"   - {user.username} ({user.email})")
            print(f"     Folders: {len(user.folders)}")
            print(f"     Bookmarks: {len(user.bookmarks)}")
            print(f"     Ratings: {len(user.recipe_ratings)}")

        print(f"\n📁 Folders: {len(folders)}")
        print(f"🔖 Bookmarks: {len(bookmarks)}")
        print(f"⭐ Ratings: {len(ratings)}")
        print(f"🔍 Search History: {len(history)}")

        print("\n" + "=" * 60)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Initialize database')
    parser.add_argument('--seed', action='store_true', help='Seed with test data from dataset')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    args = parser.parse_args()

    try:
        if args.stats:
            show_database_stats()
        else:
            init_database()

            if args.seed:
                seed_test_data()

            if not args.stats:
                print("\n🎉 Database ready to use!")
                print("\n💡 Next steps:")
                print("   1. Start backend: python app.py")
                print("   2. Start frontend: cd ../frontend && npm run dev")
                print("   3. Open browser: http://localhost:5173")
                print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
