"""
Orthographic Spell Correction Service
Uses Edit Distance (Levenshtein) to find closest matches in the vocabulary
"""

from collections import Counter
import numpy as np

class SpellChecker:
    def __init__(self, documents):
        """
        Initialize spell checker with vocabulary from documents

        Args:
            documents: DataFrame with 'name' and 'ingredient_parts' columns
        """
        self.documents = documents

        # Build vocabulary from recipe names and ingredients
        print("Building vocabulary...")
        vocab_set = set()

        # Add recipe names
        names = documents['name'].fillna('').str.lower().tolist()
        vocab_set.update([self._clean_word(name) for name in names])

        # Add ingredients
        ingredients = documents['ingredient_parts'].fillna('').tolist()
        for ing_text in ingredients:
            words = str(ing_text).lower().split()
            vocab_set.update(words)

        # Remove empty strings
        vocab_set.discard('')

        # Convert to sorted list for binary search
        self.vocabulary = sorted(list(vocab_set))

        # Build word frequency for better suggestions
        word_freq = Counter()
        for word in vocab_set:
            # Count occurrences in names (higher weight)
            for name in names:
                if word in name.lower():
                    word_freq[word] += 3

            # Count occurrences in ingredients
            for ing_text in ingredients:
                if word in str(ing_text).lower():
                    word_freq[word] += 1

        self.word_freq = dict(word_freq)

        print(f"✅ Vocabulary built: {len(self.vocabulary):,} unique words")

    def _clean_word(self, word):
        """Clean word for vocabulary"""
        word = word.lower().strip()
        # Remove special characters but keep spaces for multi-word terms
        import re
        word = re.sub(r'[^a-z\s]', '', word)
        return word

    def _levenshtein_distance(self, s1, s2):
        """
        Calculate Levenshtein distance between two strings

        Args:
            s1: first string
            s2: second string

        Returns:
            int: edit distance
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        # s1 is now the longer string
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def suggest_correction(self, query, max_suggestions=3, max_distance=2):
        """
        Suggest spelling corrections for a query

        Args:
            query: input query string
            max_suggestions: maximum number of suggestions to return
            max_distance: maximum edit distance allowed

        Returns:
            list of tuples: [(suggestion, distance), ...]
        """
        if not query or len(query) < 2:
            return []

        # Clean query
        query_clean = query.lower().strip()

        # Split query into words
        words = query_clean.split()

        suggestions = []

        for word in words:
            # Skip if word exists in vocabulary
            if word in self.vocabulary:
                continue

            # Find closest matches
            matches = []
            for vocab_word in self.vocabulary:
                # Skip if too different length (>2x or <-2x)
                if abs(len(vocab_word) - len(word)) > 2:
                    continue

                distance = self._levenshtein_distance(word, vocab_word)

                if distance <= max_distance:
                    matches.append((vocab_word, distance))

            # Sort by distance, then by frequency
            matches.sort(key=lambda x: (x[1], -self.word_freq.get(x[0], 0)))

            # Get top suggestions
            top_matches = matches[:max_suggestions]

            if top_matches:
                # Use the best match
                best_match = top_matches[0][0]
                suggestions.append((word, best_match, top_matches[0][1]))

        return suggestions

    def correct_query(self, query):
        """
        Auto-correct a query

        Args:
            query: input query string

        Returns:
            tuple: (corrected_query, corrections_made, suggestions)
        """
        if not query:
            return query, [], []

        suggestions = self.suggest_correction(query)

        if not suggestions:
            return query, [], []

        # Build corrected query
        corrected_query = query
        corrections = []

        for typo, correction, distance in suggestions:
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(typo), re.IGNORECASE)
            corrected_query = pattern.sub(correction, corrected_query)
            corrections.append({
                "original": typo,
                "correction": correction,
                "distance": distance
            })

        return corrected_query, corrections, suggestions


# Global spell checker instance
_spell_checker = None


def get_spell_checker():
    """Get or create global spell checker instance"""
    global _spell_checker
    return _spell_checker


def init_spell_checker(documents):
    """Initialize global spell checker with documents"""
    global _spell_checker
    _spell_checker = SpellChecker(documents)
    return _spell_checker


if __name__ == "__main__":
    # Test with sample data
    import pandas as pd

    # Create sample data
    sample_data = {
        'name': ['Chicken Curry', 'Spaghetti Carbonara', 'Beef Wellington', 'Chocolate Cake'],
        'ingredient_parts': ['chicken, curry, spices', 'pasta, eggs, bacon, beef, pastry, flour, chocolate, sugar']
    }

    df = pd.DataFrame(sample_data)

    # Initialize spell checker
    checker = SpellChecker(df)

    # Test queries
    test_queries = [
        "chiken curry",
        "spageti carbonara",
        "choclate cake",
        "beef welington"
    ]

    print("\n" + "=" * 60)
    print("Testing Spell Correction")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        corrected, corrections, suggestions = checker.correct_query(query)

        if corrections:
            print(f"✏️  Corrected: '{corrected}'")
            for corr in corrections:
                print(f"   {corr['original']} → {corr['correction']} (distance: {corr['distance']})")
        else:
            print("✅ No corrections needed")
