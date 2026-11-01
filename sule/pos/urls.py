from  django.urls  import path
from . import views
urlpatterns=[
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('new_sales/', views.new_sales, name='new_sales'),
    path('sales/', views.sales, name='sales'),
    path('sale/<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('logout/', views.logout, name='logout'),
    path('owner_dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('reports/', views.reports , name='reports'),
    path('report_detail/<str:report_type>/', views.report_detail, name='report_detail'),
    path('download_report-pdf/<str:report_type>/',views.download_report_pdf, name='download_report_pdf'),
    path('categories/', views.categories, name='categories'),
    path('products/',views.products, name='products'),
    path('sellers/', views.sellers, name='sellers'),
    path('add-stock/<int:product_id>/', views.add_stock, name='add_stock'),
    path('delete_product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('delete_all_products/', views.delete_all_products, name='delete_all_products'),
    path('expenses/', views.expenses, name='expenses'),
    path('loans/', views.loans, name='loans'),
    path('agency/', views.agency, name='agency'),
    path('agency/pdf/<int:report_id>/', views.agency_pdf, name='agency_pdf'),
   




]