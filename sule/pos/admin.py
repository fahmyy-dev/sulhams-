from django.contrib import admin
from . models import Category, Product , SaleItem , Sale , UserProfile, Expense,Loan,AgencyLoan,AgencyNetwork,AgencyReport
admin.site.register(Category)
admin.site.register(UserProfile)
admin.site.register(Product)
admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(Expense)
admin.site.register(Loan)
admin.site.register(AgencyLoan)
admin.site.register(AgencyReport)
admin.site.register(AgencyNetwork)
# Register your models here.
