from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count
from .models import ChatSession, Message


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_title', 'user_display', 'message_count', 'created_at_display', 'view_session_link', 'status_badge']
    list_filter = ['created_at', 'user']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'session_preview']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('title', 'user', 'created_at')
        }),
        ('Preview', {
            'fields': ('session_preview',),
            'classes': ('collapse',)
        }),
    )
    
    def session_title(self, obj):
        """Display session title with icon"""
        return format_html(
            '<i class="fas fa-comments"></i> &nbsp; <strong>{}</strong>',
            obj.title[:40]
        )
    session_title.short_description = 'Session Title'
    
    def user_display(self, obj):
        """Display user with role badge"""
        user_type = getattr(obj.user, 'user_type', 'student').upper()
        colors = {'ADMIN': '#dc3545', 'TEACHER': '#ffc107', 'STUDENT': '#0dcaf0'}
        color = colors.get(user_type, '#6c757d')
        
        return format_html(
            '<strong>{}</strong> <span style="background: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 5px;">{}</span>',
            obj.user.username,
            color,
            user_type
        )
    user_display.short_description = 'User'
    
    def message_count(self, obj):
        """Display message count with icon"""
        count = obj.messages.count()
        return format_html(
            '<span style="background: #e3f2fd; padding: 5px 10px; border-radius: 4px; font-weight: bold;">{} 💬</span>',
            count
        )
    message_count.short_description = 'Messages'
    
    def created_at_display(self, obj):
        """Display creation date with icon"""
        if obj.created_at:
            return format_html(
                '<i class="fas fa-calendar-alt"></i> &nbsp; {}',
                obj.created_at.strftime('%b %d, %Y %H:%M')
            )
        return '-'
    created_at_display.short_description = 'Created'
    
    def view_session_link(self, obj):
        """Add link to view session detail"""
        url = reverse('chat:session_detail', args=[obj.id])
        return format_html(
            '<a class="button" style="background-color: #417690;" href="{}">👁️ View</a>',
            url
        )
    view_session_link.short_description = 'Action'
    
    def status_badge(self, obj):
        """Show session status"""
        message_count = obj.messages.count()
        if message_count == 0:
            status = 'NEW'
            color = '#28a745'
        elif message_count < 5:
            status = 'ACTIVE'
            color = '#0dcaf0'
        else:
            status = 'LONG'
            color = '#6f42c1'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            status
        )
    status_badge.short_description = 'Status'
    
    def session_preview(self, obj):
        """Show preview of all messages in session"""
        messages = obj.messages.all()[:10]
        if not messages:
            return '📭 No messages yet'
        
        preview_html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; max-height: 400px; overflow-y: auto;">'
        
        for msg in messages:
            icon = '👤' if msg.message_type == 'user' else '🤖'
            msg_type = '<strong>User:</strong>' if msg.message_type == 'user' else '<strong>Bot:</strong>'
            preview_html += f'<div style="margin-bottom: 10px; padding: 10px; background: white; border-left: 3px solid {"#0dcaf0" if msg.message_type == "user" else "#667eea"}; border-radius: 4px;">'
            preview_html += f'{icon} {msg_type} {msg.content[:100]}{"..." if len(msg.content) > 100 else ""}</div>'
        
        preview_html += '</div>'
        return format_html(preview_html)
    session_preview.short_description = 'Message Preview'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['message_type_display', 'content_preview', 'session_info', 'confidence_display', 'created_at_display']
    list_filter = ['message_type', 'created_at', 'session__user']
    search_fields = ['content', 'session__title', 'session__user__username']
    readonly_fields = ['created_at', 'session', 'message_type', 'content', 'confidence_score']
    
    fieldsets = (
        ('Message Details', {
            'fields': ('session', 'message_type', 'content', 'confidence_score', 'created_at')
        }),
    )
    
    def has_add_permission(self, request):
        """Don't allow manual message creation"""
        return False
    
    def message_type_display(self, obj):
        """Display message type with icon and color"""
        if obj.message_type == 'user':
            return format_html(
                '<span style="background: #e3f2fd; color: #0d47a1; padding: 5px 10px; border-radius: 4px; font-weight: bold;">👤 User</span>'
            )
        else:
            return format_html(
                '<span style="background: #f3e5f5; color: #6a1b9a; padding: 5px 10px; border-radius: 4px; font-weight: bold;">🤖 Bot</span>'
            )
    message_type_display.short_description = 'Type'
    
    def content_preview(self, obj):
        """Show message content with truncation"""
        content = obj.content[:80]
        tooltip = obj.content.replace('"', '&quot;')
        
        return format_html(
            '<span title="{}">{}{}</span>',
            tooltip,
            content,
            '...' if len(obj.content) > 80 else ''
        )
    content_preview.short_description = 'Message'
    
    def session_info(self, obj):
        """Show session and user info"""
        return format_html(
            '<strong>{}</strong><br><small style="color: #666;">👤 {}</small>',
            obj.session.title[:30],
            obj.session.user.username
        )
    session_info.short_description = 'Session'
    
    def confidence_display(self, obj):
        """Display confidence score with color coding"""
        if obj.confidence_score is None:
            return '—'
        
        score = obj.confidence_score * 100
        if score >= 80:
            color = '#28a745'
            emoji = '✅'
        elif score >= 60:
            color = '#ffc107'
            emoji = '⚠️'
        else:
            color = '#dc3545'
            emoji = '❌'
        
        return format_html(
            '{} <span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{:.0f}%</span>',
            emoji,
            color,
            score
        )
    confidence_display.short_description = 'Confidence'
    
    def created_at_display(self, obj):
        """Display timestamp"""
        return format_html(
            '{}',
            obj.created_at.strftime('%b %d, %H:%M:%S')
        )
    created_at_display.short_description = 'Created'
