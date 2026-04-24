from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    """Extended user profile with role tracking"""
    USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='student')
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.user_type})"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class ResponseFeedback(models.Model):
    """Tracks student feedback on bot responses"""
    RATING_CHOICES = [
        (1, '😞 Not Helpful'),
        (2, '😐 Somewhat Helpful'),
        (3, '🙂 Helpful'),
        (4, '😊 Very Helpful'),
        (5, '😍 Excellent'),
    ]
    
    from chat.models import Message
    message = models.ForeignKey('chat.Message', on_delete=models.CASCADE, related_name='feedback')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} rated message {self.message.id}: {self.rating}/5"


class LearningGap(models.Model):
    """Tracks student knowledge gaps for SRL support"""
    TOPIC_CHOICES = [
        ('sql', 'SQL Queries'),
        ('normalization', 'Database Normalization'),
        ('joins', 'JOIN Operations'),
        ('indexing', 'Database Indexing'),
        ('transactions', 'Transactions & ACID'),
        ('relationships', 'Table Relationships'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_gaps')
    topic = models.CharField(max_length=50, choices=TOPIC_CHOICES)
    incorrect_attempts = models.IntegerField(default=0)
    suggested_resources = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_mentioned = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'topic')
        ordering = ['-last_mentioned']
    
    def __str__(self):
        return f"{self.user.username} - {self.topic} (attempts: {self.incorrect_attempts})"


class TAMSurvey(models.Model):
    """Technology Acceptance Model survey tracking"""
    SCALE_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tam_surveys')
    # Perceived Usefulness
    pu_score = models.IntegerField(choices=SCALE_CHOICES, help_text="Perceived Usefulness (1-5)")
    # Ease of Use
    eou_score = models.IntegerField(choices=SCALE_CHOICES, help_text="Ease of Use (1-5)")
    # Attitude toward Using
    attitude_score = models.IntegerField(choices=SCALE_CHOICES, help_text="Attitude (1-5)")
    # Behavioral Intention
    intention_score = models.IntegerField(choices=SCALE_CHOICES, help_text="Intention to Use (1-5)")
    
    feedback = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-completed_at']
    
    def __str__(self):
        return f"{self.user.username} - TAM Survey"
    
    @property
    def average_score(self):
        return (self.pu_score + self.eou_score + self.attitude_score + self.intention_score) / 4
