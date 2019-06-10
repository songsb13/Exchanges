from django.conf.urls import url

from . import views

urlpatterns = [
    url('v0.1/public/current_data/', views.current_data, name='current_data'),
    url('v0.1/private/balance/', views.balance, name='balance'),
]