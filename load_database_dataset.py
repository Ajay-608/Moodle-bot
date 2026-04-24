"""
Populate database with SQL/Database Q&A dataset
Simple version that works around import issues
"""
import os
import sys
import django
import json
import traceback

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')

print("🔧 Initializing Django...")
try:
    django.setup()
    print("✅ Django initialized")
except Exception as e:
    print(f"❌ Django setup error: {e}")
    traceback.print_exc()
    sys.exit(1)

from knowledge.models import Document
from django.utils import timezone

def load_database_dataset():
    """Load SQL/Database Q&A from JSON into Document model"""
    
    json_path = 'database_dataset.json'
    
    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        return False
    
    try:
        print("\n📖 Loading dataset...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        topics = data.get('database_topics', [])
        print(f"📊 Found {len(topics)} topics in dataset")
        
        created_count = 0
        updated_count = 0
        
        # Clear old documents to avoid duplicates
        existing = Document.objects.filter(course_id=1)
        print(f"🗑️  Clearing {existing.count()} existing documents...")
        existing.delete()
        
        print("\n📝 Creating documents...\n")
        
        for topic in topics:
            # Create comprehensive content combining Q&A with metadata
            content = f"""# {topic.get('question', 'N/A')}

## Answer:
{topic.get('answer', 'N/A')}

## Key Concepts:
{', '.join(topic.get('keywords', []))}

## Difficulty Level:
{topic.get('difficulty', 'intermediate').upper()}

## Examples:
{chr(10).join(f'- {ex}' for ex in topic.get('examples', []))}

## Category:
{topic.get('category', 'General')}
"""
            
            try:
                doc, created = Document.objects.get_or_create(
                    title=topic.get('question', 'Untitled'),
                    course_id=1,  # CS401 - Database Systems
                    defaults={
                        'content': content.strip(),
                        'chunk_id': topic.get('id'),
                        'created_at': timezone.now()
                    }
                )
                
                if created:
                    created_count += 1
                    print(f"   ✅ {topic.get('category')}: {topic.get('question')[:50]}...")
                else:
                    # Update if already exists
                    doc.content = content.strip()
                    doc.save()
                    updated_count += 1
            
            except Exception as e:
                print(f"   ❌ Error with {topic.get('question')[:30]}: {e}")
                continue
        
        total_docs = Document.objects.filter(course_id=1).count()
        
        print(f"\n✅ Load Complete!")
        print(f"📈 Summary:")
        print(f"   ✅ Created: {created_count} documents")
        print(f"   📝 Updated: {updated_count} documents")
        print(f"   📊 Total: {total_docs} documents in database")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Loading Database Dataset...")
    print("=" * 60)
    success = load_database_dataset()
    print("=" * 60)
    if success:
        print("\n✅ Dataset loaded successfully!")
    else:
        print("\n❌ Failed to load dataset")
        sys.exit(1)

