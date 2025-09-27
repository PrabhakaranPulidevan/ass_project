from django.urls import path
from ex_fil import views

urlpatterns = [
    path('etl-sales/', views.etl_sales_view, name='etl_sales'),
]
