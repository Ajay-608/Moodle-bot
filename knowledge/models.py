from django.db import models
from django.utils import timezone

class Document(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    course_id = models.IntegerField(default=401)  # CS401
    embedding = models.JSONField(null=True, blank=True, default=dict)
    chunk_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'knowledge_document'
    
    def __str__(self):
        return self.title
