import json

# Test dataset loading
try:
    with open('database_dataset.json', 'r') as f:
        data = json.load(f)
    
    topics = data.get('database_topics', [])
    print(f'✅ Dataset loaded successfully!')
    print(f'📊 Total topics: {len(topics)}')
    
    # Show first 3 topics
    for i, topic in enumerate(topics[:3], 1):
        print(f'\n{i}. {topic["question"][:60]}...')
        print(f'   Category: {topic["category"]}')
        print(f'   Difficulty: {topic["difficulty"]}')
    
except Exception as e:
    print(f'❌ Error: {e}')
