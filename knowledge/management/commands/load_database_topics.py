from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from knowledge.models import Document
import json
import os


class Command(BaseCommand):
    help = 'Load database SQL/Database Q&A dataset into knowledge base'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            dest='clear',
            default=False,
            help='Clear existing documents before loading',
        )
        parser.add_argument(
            '--course-id',
            type=int,
            dest='course_id',
            default=1,
            help='Course ID to associate documents with (default: 1)',
        )
    
    def handle(self, *args, **options):
        course_id = options['course_id']
        should_clear = options['clear']
        
        # Load JSON dataset
        dataset_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', '..', 
            'database_dataset.json'
        )
        
        if not os.path.exists(dataset_path):
            raise CommandError(f'Dataset file not found: {dataset_path}')
        
        try:
            with open(dataset_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in dataset: {e}')
        
        topics = data.get('database_topics', [])
        
        if not topics:
            raise CommandError('No topics found in dataset')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'📊 Found {len(topics)} database topics in dataset'
            )
        )
        
        # Clear existing documents if requested
        if should_clear:
            existing = Document.objects.filter(course_id=course_id)
            count = existing.count()
            existing.delete()
            self.stdout.write(
                self.style.WARNING(f'🗑️  Deleted {count} existing documents')
            )
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for topic in topics:
            try:
                # Build comprehensive content
                content = self._build_content(topic)
                
                doc, created = Document.objects.get_or_create(
                    title=topic.get('question', 'Untitled'),
                    course_id=course_id,
                    defaults={
                        'content': content,
                        'chunk_id': topic.get('id'),
                        'created_at': timezone.now()
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Created: {topic.get("category")} - '
                            f'{topic.get("question", "N/A")[:50]}'
                        )
                    )
                else:
                    # Update existing document
                    doc.content = content
                    doc.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'📝 Updated: {topic.get("category")} - '
                            f'{topic.get("question", "N/A")[:50]}'
                        )
                    )
            
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Error with {topic.get("question", "Unknown")}: {e}'
                    )
                )
        
        # Summary
        total_docs = Document.objects.filter(course_id=course_id).count()
        
        summary = f'\n📈 Summary:\n'
        summary += f'   ✅ Created: {created_count} documents\n'
        summary += f'   📝 Updated: {updated_count} documents\n'
        summary += f'   ❌ Errors: {error_count} topics\n'
        summary += f'   📊 Total: {total_docs} documents in knowledge base\n'
        summary += f'   📌 Course ID: {course_id}'
        
        self.stdout.write(self.style.SUCCESS(summary))
    
    def _build_content(self, topic):
        """Build formatted content from topic data"""
        parts = []
        
        # Title
        parts.append(f"# {topic.get('question', 'N/A')}\n")
        
        # Answer
        parts.append("## 📚 Answer:")
        parts.append(f"{topic.get('answer', 'N/A')}\n")
        
        # Keywords
        keywords = topic.get('keywords', [])
        if keywords:
            parts.append("## 🏷️ Keywords:")
            parts.append(f"{', '.join(keywords)}\n")
        
        # Difficulty
        difficulty = topic.get('difficulty', 'intermediate').upper()
        parts.append("## 📊 Difficulty Level:")
        parts.append(f"{difficulty}\n")
        
        # Examples
        examples = topic.get('examples', [])
        if examples:
            parts.append("## 💻 Examples:")
            for ex in examples:
                parts.append(f"```sql\n{ex}\n```")
            parts.append("")
        
        # Category
        category = topic.get('category', 'General')
        parts.append("## 📂 Category:")
        parts.append(f"{category}\n")
        
        return '\n'.join(parts).strip()
