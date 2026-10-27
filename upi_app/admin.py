from django.contrib import admin
from django.utils.html import format_html
from .models import UserProfile, Transaction, Feedback, LocationHistory

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'upi_id', 'phone_number', 'balance', 'is_verified', 'trust_score')
    search_fields = ('user__username', 'upi_id', 'phone_number')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver_upi_id', 'amount', 'colored_status', 'fraud_score', 'is_suspicious', 'timestamp')
    list_filter = ('status', 'timestamp', 'is_suspicious')
    search_fields = ('sender__username', 'receiver_upi_id')

    def colored_status(self, obj):
        if obj.status == 'BLOCKED':
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.status)
        elif obj.status == 'PENDING_VERIFICATION':
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', obj.status)
        elif obj.status == 'SUCCESS':
            return format_html('<span style="color: green;">{}</span>', obj.status)
        return obj.status
    colored_status.short_description = 'Status'

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'is_resolved')
    list_filter = ('is_resolved', 'created_at')

@admin.register(LocationHistory)
class LocationHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'latitude', 'longitude', 'timestamp', 'ip_address')
    list_filter = ('timestamp',)
