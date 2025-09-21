from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'main'

def redirect_to_inspection_list(request):
    """Redirect root URL to inspection list"""
    return redirect('main:inspection_list')

urlpatterns = [
    path('', redirect_to_inspection_list, name='home'),
    path('about/', views.about, name='about'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('configuration/', views.configuration, name='configuration'),
    path('inspections/', views.inspection_list, name='inspection_list'),
    path('inspection/<int:inspection_id>/', views.inspection_detail, name='inspection_detail'),
]

