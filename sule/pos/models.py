from django.contrib.auth.models import User
from django.db import models
from django.db import models
from django.conf import settings
from decimal import Decimal
#class user


class UserProfile(models.Model):
    ROLE_CHOICES=(
        ('OWNER', 'Owner'),
        ('SELLER','Seller'),
    )
    user=models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile' 
    )
    role=models.CharField(max_length=10, choices=ROLE_CHOICES)
    def __str__(self):
        return f"{self.user.username} - {self.role}"

#class category
class Category(models.Model):
    name=models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name


# Class product
class Product(models.Model):
    name=models.CharField(max_length=100)
    brand=models.CharField(max_length=100)
    category=models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    size=models.CharField(max_length=50, blank=True)
    code=models.CharField(max_length=50, unique=True)
    buying_price=models.DecimalField(max_digits=10, decimal_places=2)
    selling_price=models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity=models.PositiveBigIntegerField(default=0)
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.name} - {self.code}"

#class sale
class Sale(models.Model):
    PAYMENT_CHOICES=(
        ('CASH','Cash'),
        ('MOBILE','Mobile'),
        ('CARD','Card'),
    )  
    sale_number=models.CharField(max_length=10, unique=True, blank=True) 
    seller=models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales')
    sale_date=models.DateField(auto_now_add=True)
    payment_method=models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='CASH')
    subtotal=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.sale_number
    @property
    def total_profit(self):
        return sum(item.profit for item in self.items.all())

#sale_items
class SaleItem(models.Model):
    sale=models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')  
    product=models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')  
    quantity=models.PositiveBigIntegerField()
    buying_price=models.DecimalField(max_digits=10, decimal_places=2)
    selling_price=models.DecimalField(max_digits=10, decimal_places=2)
    total=models.DecimalField(max_digits=10, decimal_places=2)
    profit=models.DecimalField(max_digits=10, decimal_places=2)
    def __str__(self):
        return f"{self.product.name} - {self.quantity}"



    #expenses class
    
class Expense(models.Model):
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - TSh {self.amount}"

    class Meta:
        ordering = ['-date', '-created_at']


 #class loan
 

class Loan(models.Model):

    customer_name = models.CharField(
        max_length=150
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    loan_date = models.DateField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-loan_date", "-id"]

    def __str__(self):
        return f"{self.customer_name} - TSh {self.amount}"       

#class wakala //agency



class AgencyReport(models.Model):
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agency_reports'
    )
    report_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-report_date', '-created_at']

    def __str__(self):
        return f"Agency Report - {self.seller} - {self.report_date}"


class AgencyNetwork(models.Model):

    NETWORK_CHOICES = [
        ('HALOTEL', 'Halotel'),
        ('VODACOM', 'Vodacom'),
        ('AIRTEL', 'Airtel'),
        ('YAS', 'Yas'),
    ]

    report = models.ForeignKey(
        AgencyReport,
        on_delete=models.CASCADE,
        related_name='networks'
    )

    network = models.CharField(
        max_length=20,
        choices=NETWORK_CHOICES
    )

    cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    float_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        unique_together = ('report', 'network')

    @property
    def total_loans(self):
        return self.loans.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    @property
    def network_total(self):
        return self.cash + self.float_amount + self.total_loans

    def __str__(self):
        return f"{self.get_network_display()} - {self.report.report_date}"


class AgencyLoan(models.Model):

    network = models.ForeignKey(
        AgencyNetwork,
        on_delete=models.CASCADE,
        related_name='loans'
    )

    borrower_name = models.CharField(max_length=150)

    loan_date = models.DateField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-loan_date', '-created_at']

    def __str__(self):
        return f"{self.borrower_name} - {self.amount}"