#!/usr/bin/env python
"""
Test the chatbot search functionality
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')
django.setup()

from chat.views import search_knowledge_base

# Test queries
test_queries = [
    "What is SQL?",
    "Explain database joins",
    "What is normalization?",
    "How do I write a SELECT statement?",
    "What are primary keys?",
    "Explain transactions",
    "How does indexing improve performance?",
    "What is a stored procedure?"
]

print("🧪 Testing Chatbot Knowledge Base Search")
print("=" * 70)

for query in test_queries:
    print(f"\n🔍 Query: '{query}'")
    
    answer, confidence, sources = search_knowledge_base(query)
    
    if answer:
        # Show first 150 chars of answer
        answer_preview = answer[:150].replace('\n', ' ').strip()
        print(f"✅ Found ({confidence*100:.0f}% confidence)")
        print(f"   Answer: {answer_preview}...")
        print(f"   Sources: {', '.join(sources)}")
    else:
        print(f"❌ No relevant documents found")

print("\n" + "=" * 70)
print("✅ Test Complete!")
