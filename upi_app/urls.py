"""
URL configuration for Fraudshield project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views

urlpatterns = [
    # User URLs
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('profile/', views.profile, name='profile'),
    path('balance/', views.balance, name='balance'),
    path('history/', views.history, name='history'),
    path('send/', views.send_money, name='send_money'),
    path('feedback/', views.feedback, name='feedback'),
    path('verify-emergency/<int:txn_id>/', views.verify_emergency, name='verify_emergency'),
    path('finalize-emergency/<int:txn_id>/', views.finalize_emergency_pay, name='finalize_emergency_pay'),
    path('verify-pin/', views.verify_pin, name='verify_pin'),
    path('api/get-receiver-details/', views.get_receiver_details, name='get_receiver_details'),
    path('expense-summary/', views.expense_summary, name='expense_summary'),
    path('verify-account/', views.verify_account, name='verify_account'),
    path('logout/', views.logout_view, name='logout'),


    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('view-feedbacks/', views.view_feedbacks, name='view_feedbacks'),
    path('reply-feedback/<int:feedback_id>/', views.reply_feedback, name='reply_feedback'),
    path('verify-merchant/<int:user_id>/<str:action>/', views.verify_merchant, name='verify_merchant'),
    path('delete-feedback/<int:feedback_id>/', views.delete_feedback, name='delete_feedback'),
]
