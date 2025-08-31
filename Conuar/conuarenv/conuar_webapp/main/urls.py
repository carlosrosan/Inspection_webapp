from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('services/', views.services, name='services'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('protected/', views.protected_home, name='protected_home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('inspections/', views.inspection_list, name='inspection_list'),
    path('inspection/<int:inspection_id>/', views.inspection_detail, name='inspection_detail'),
]

