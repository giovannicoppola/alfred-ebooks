Test usage of new proximity search feature:

# Basic 2-word search (automatically uses proximity within 100 words)
searchEPUB.py "love death" --alfred

# Custom proximity distance (50 words)  
searchEPUB.py "king battle" --proximity=50 --alfred

# Single word search (uses regular exact matching)
searchEPUB.py "shakespeare" --alfred

# 3+ word search (uses regular exact matching)
searchEPUB.py "to be or not to be" --alfred

The proximity search will only activate when:
1. Exactly 2 words are provided in the search term
2. Both words are found in the text
3. They appear within the specified distance (default 100 words)

Results will show:
- "word1 ... word2 (N words apart)" as the match text
- Context around both words
- Distance information in the match details