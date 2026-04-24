from django.db import models
from django.contrib.auth.models import User  # ✅ Direct import = NO ERRORS

class ChatSession(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='chat_sessions'  # ✅ Unique reverse name
    )
    title = models.CharField(max_length=200, default="Database Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title[:30]}"

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User'), 
        ('bot', 'Bot')
    ]
    
    session = models.ForeignKey(
        ChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages'  # ✅ Unique reverse name
    )
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    confidence_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}..."
