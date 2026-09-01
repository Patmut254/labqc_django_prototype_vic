from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("registration/", views.registration, name="registration"),
    path("slump-test/", views.slump_test, name="slump_test"),
    path("curing-strength/", views.curing_strength, name="curing_strength"),
    path("reporting/", views.reporting, name="reporting"),
    path("search/", views.sample_search, name="sample_search"),
    path("login/", auth_views.LoginView.as_view(template_name="qc/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
]
