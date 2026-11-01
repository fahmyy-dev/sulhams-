from django.contrib.auth import authenticate, login as auth_login , logout as auth_logout
from django.contrib import messages
from datetime import timedelta
from datetime import date
from django.contrib.auth.models import User
from django.db.models import Q ,Sum
from django.utils import timezone
from django.db.models.deletion import ProtectedError
from . models import Sale, SaleItem , Category , Product , UserProfile,Expense,Loan,AgencyReport, AgencyNetwork, AgencyLoan
from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from decimal import Decimal, InvalidOperation
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


from django.utils.dateparse import parse_date


# HOME VIEW
def home(request):
    if request.user.is_authenticated:
        return redirect('sales')

    return render(request, 'pos/home.html')


# LOGIN VIEW
def login(request):

    if request.user.is_authenticated:
        return redirect('sales')

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            auth_login(request, user)
            return redirect('sales')

        else:
            messages.error(
                request,
                'Invalid Username or Password'
            )

    return render(request, 'pos/home.html')

#logout view
def logout(request):
    auth_logout(request)
    return redirect('login')
#sales view
@login_required
def sales(request):
    sales=Sale.objects.all().order_by('created_at')
    today=timezone.localdate()
    total_sales=0
    search=request.GET.get('search')
    
          
    seller_id=request.GET.get('seller')
    if seller_id:
        sales=sales.filter(seller_id=seller_id)
    payment_method=request.GET.get('payment')
    if payment_method:
        sales=sales.filter(payment_method)
    period=request.GET.get('period')
    date_from=request.GET.get('date_from')
    date_to=request.GET.get('date_to')
    if search:
        sales=sales.filter(
            Q(sale_number__icontains=search )|
            Q(seller__username__icontains=search ) |
            Q(items__product__name__icontains=search)|
            Q(items__product__brand__icontains=search)|
            Q(items__product__code__icontains=search) 
        ).distinct()
    if seller_id:
            sales= sales.filter(seller_id=seller_id)
    if payment_method:
            sales= sales.filter(payment_method=payment_method)
            
    if period=='day':
            sales= sales.filter(sale_date=today) 
    elif period=='week':
            sales= sales.filter(sale_date__week=today.isocalendar().week , sale_date__year=today.year)  
    elif period=='month':
            sales=sales.filter(sale_date__month=today.month, sale_date__year=today.year)
    elif period=='year':
            sales= sales.filter(sale_date__year=today.year)   
    if date_from:
            sales=sales.filter(sale_date__gte=date_from)
    if date_to:
            sales=sales.filter(sale_date__lte=date_to)   
    total_sales=sales.aggregate(total=Sum('total'))['total'] or 0 
    sellers=Sale.objects.values('seller__id', 'seller__username') .distinct() 
    today_sales=Sale.objects.filter(sale_date=today).aggregate(total=Sum('total')) ['total'] or 0
    today_profit=Sale.objects.filter(sale_date=today).aggregate(total=Sum('items__profit'))['total'] or 0    
    transaction_count=Sale.objects.filter(sale_date=today).count()    
        
    return render(request, 'pos/sales.html',{'sales':sales, 'total_sales':total_sales, 'today_sales' :today_sales,'today_profit':today_profit,'sellers': sellers ,'transaction_count':transaction_count})
#new_sale view

def new_sales(request):
    products=Product.objects.all()
    categories=Category.objects.all().order_by('name')
    if request.method=='POST':
        product_ids=request.POST.getlist('product_id[]') or request.POST.getlist('product_id')
        quantities=request.POST.getlist('quantity[]') or request.POST.getlist('quantity')
        sale_date=request.POST.get('sale_date')
        discount=Decimal(request.POST.get('discount') or'0')
        if discount<0:
            raise ValueError('Discount cannot be negative')
        payment_method=request.POST.get('payment_method')
        if not product_ids or not quantities:
            print("PRODUCT IDS:" , product_id)
            print("QUANTITIES:", quantities)
            messages.error(request, 'Please select atleast one product')
            return redirect('new_sales')
        if len(product_ids) !=len(quantities):
            messages.error(request, 'Invalid sale data.')
            return redirect('new_sale')
        try:
            with transaction.atomic():
             sale= Sale.objects.create(
                 sale_number=f"SALE-{uuid.uuid4().hex[:8].upper()}", 
                 seller=request.user,
                 sale_date=sale_date,
                 payment_method=payment_method, 
                 total=Decimal('0.00')                      
                )
            grand_total=Decimal('0.00')
            for product_id, quantity in zip(  product_ids, quantities):
                product=Product.objects.select_for_update().get(
                  id=product_id,
                  is_active=True
                  ) 
                quantity=int(quantity) 
                if quantity<=0:
                   raise
                ValueError('Quantity must be greater tha zero.')
                if quantity>product.stock_quantity:
                 raise ValueError(f'Not enough stock for {product.name}.' f'Available stock:{product.stock_quantity}')    
                buying_price=product.buying_price
                selling_price=Decimal(str(int(round(float(product.selling_price)))))
                item_total=Decimal(str(int(round(float(selling_price*quantity)))))
                item_profit=(selling_price - buying_price)*quantity
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    buying_price=buying_price,
                    selling_price=selling_price,
                    total=item_total,
                    profit=item_profit
                )
                product.stock_quantity-= quantity
                product.save(update_fields=['stock_quantity'])
                grand_total+=item_total

            subtotal=grand_total    
            

            if discount>subtotal:
               raise ValueError('Discount cannot be greater tha subtotal')
            total_after_discount=subtotal-discount
            sale.subtotal=subtotal
            sale.discount=discount
            sale.total= total_after_discount
            sale.save(update_fields=['total','subtotal','discount'])
            items=sale.items.all()
            for item in items:
                item_discount=(item.total / subtotal)*discount
                item.profit=(item.selling_price*item.quantity)-(item.buying_price*item.quantity)-item_discount
                item.save(update_fields=['profit'])
            messages.success(request, 'Sale completed Successiful')
            return redirect('sale_detail', sale_id=sale.id)
        except Product.DoesNotExist:
                messages.error(request, 'One of the selected product was not found.')
        except ValueError as e:
                messages.error(request, str(e))
        except Exception as e:
                messages.error(request, f'sale failed:{e}.')    
        

    return render(request, 'pos/new_sales.html', {'products':products, 'categories':categories,'today':timezone.localdate()})
#sale_detail

def sale_detail(request, sale_id):
    sale= get_object_or_404(Sale,  id=sale_id)
    items=SaleItem.objects.filter(sale=sale)
    subtotal=Sum(item.quantity* item.price for item in items)
    discount=Sale.discount if hasattr(Sale, 'discount') else 0
    total_items=sum(item.quantity for item in items)
    return render(request, 'pos/sale_detail.html' , {'sale':sale, 'items':items , 'total_items':total_items,'subtotal':subtotal,'discount':discount})
#OWNER DASHBOrd
@login_required
def owner_dashboard(request):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role !='OWNER':
        return redirect('sales')
    today=timezone.localdate()
    week_start=today - timedelta(days=today.weekday())
    month_start=today.replace(day=1)
    year_start=today.replace(month=1, day=1)
    total_sales=Sale.objects.aggregate(total=Sum('total'))['total'] or 0
    total_profit=SaleItem.objects.aggregate(total=Sum('profit'))['total'] or 0
    total_expenses=Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_loans=Loan.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_net_profit=total_profit-total_expenses
    product_count=Product.objects.filter(is_active=True).count()
    total_stock=Product.objects.filter(is_active=True).aggregate(total=Sum('stock_quantity'))['total'] or 0
    today_sales=Sale.objects.filter(sale_date__gte=today,sale_date__lte=today).aggregate(total=Sum('total'))['total'] or 0
    week_sales=Sale.objects.filter(sale_date__gte=week_start,sale_date__lte=today).aggregate(total=Sum('total'))['total'] or 0
    month_sales=Sale.objects.filter(sale_date__gte=month_start, sale_date__lte=today).aggregate(total=Sum('total'))['total'] or 0
    year_sales=Sale.objects.filter(sale_date__gte=year_start, sale_date__lte=today).aggregate(total=Sum('total'))['total'] or 0
    recent_sales=Sale.objects.select_related('seller').prefetch_related( 'items__product').order_by('-created_at')[:5]
    low_stock_products=Product.objects.filter(is_active=True, stock_quantity__lte=5).order_by('stock_quantity')[:10]
    context={
        'total_sales':total_sales,
        'total_profit':total_profit,
        'product_count':product_count,
        'total_stock':total_stock,
        'today_sales':today_sales,
        'week_sales':week_sales,
        'month_sales':month_sales,
        'year_sales':year_sales,
        'total_expenses':total_expenses,
        'total_net_profit':total_net_profit,
        'recent_sales':recent_sales,
        'low_stock_products':low_stock_products,
        'total_loans':total_loans,

        }

    return render(request, 'pos/owner_dashboard.html', context)
#Category
@login_required
def categories(request):
    profile=getattr(request.user,'profile',None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    if request.method=='POST':
        name=request.POST.get('name')
        if name:
            Category.objects.create( name=name)
            return redirect('categories')
    categories=Category.objects.all().order_by('name')
    return render(request, 'pos/categories.html', {'categories': categories })


#products
@login_required
def products(request):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    categories=Category.objects.all().order_by('name')
    if request.method=='POST':
        name=request.POST.get('name')
        brand=request.POST.get('brand')
        category_id=request.POST.get('category')
        size=request.POST.get('size')
        code=request.POST.get('code')
        buying_price=request.POST.get('buying_price')
        selling_price=request.POST.get('selling_price')
        stock_quantity=request.POST.get('stock_quantity')
        category=Category.objects.get(id=category_id)
        Product.objects.create(
            name=name,
            brand=brand,
            category=category,
            size=size,
            code=code,
            buying_price=buying_price,
            selling_price=selling_price,
            stock_quantity=stock_quantity
        )
        return redirect('products')
    products=Product.objects.prefetch_related('category').filter(is_active=True).order_by('name')
    return render(request, 'pos/products.html',{'products':products, 'categories':categories})

#seller view
@login_required
def sellers(request):
    profile= getattr(request.user, 'profile',None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    if request.method=='POST':
        username=request.POST.get('username')
        password=request.POST.get('password')
        user= User.objects.create_user(
            username=username,
            password=password )
        UserProfile.objects.create(
            user=user,
            role='SELLER'
        )
        return redirect('sellers')
    sellers=User.objects.filter(
        profile__role='SELLER'
    ).order_by('username')
    return render(request, 'pos/sellers.html',{'sellers':sellers})

#ADD stock
@login_required
def add_stock(request, product_id):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    product=Product.objects.get(id=product_id)
    if request.method=='POST':
        quantity=int(request.POST.get('quantity'))
        if quantity>0:
            product.stock_quantity +=quantity
            product.save()
    return redirect('products')     

#delete product
@login_required
def delete_product(request, product_id):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    if request.method=='POST':
       product=get_object_or_404(Product,id=product_id)
    try:
           product.delete()
           messages.success(request, 'Product deleted successfully')
    except ProtectedError:
           messages.error(request, 'This product cannot be deleted because it has sale history')
    return redirect('products')   

@login_required
def delete_all_products(request):
        profile=getattr(request.user, 'profile', None)
        if profile is None or profile.role != 'OWNER':
            return redirect('sales')
        if request.method=='POST':
            products=Product.objects.all()
            deleted_count=0
            protected_count=0
            for product in products:
                try:
                    product.delete()
                    deleted_count+=1
                except ProtectedError:
                    protected_count+=1
            if deleted_count>0:
                messages.success(request, f'{deleted_count} product(s) deleted successfully')  
        return redirect('products')   
                   
#REPORT
@login_required
def reports(request):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role !='OWNER':
        return redirect('sales')
    return render(request, 'pos/reports.html')

#report details
@login_required
def report_detail(request, report_type):
    profile=getattr(request.user, 'profile', None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')
    today= timezone.localdate()
    if report_type == 'daily':
        start_date= today
        end_date= today
        report_title= 'Daily Sales Report'
    elif report_type == 'weekly':
        start_date= today -timedelta(days=today.weekday())
        end_date= today
        report_title= 'Weekly Sales Report'
    elif report_type == 'monthly':
        start_date= today.replace(day=1)
        end_date= today
        report_title= 'Monthly Sales Report' 
    elif report_type == 'yearly':
        start_date= today.replace(month=1, day=1) 
        end_date = today
        report_title= 'Yearly Sales Report'    
    else:
        messages.error(request, 'Invalid report type')      
        return redirect('reports') 
    sales= (
        Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date
        )
        .select_related('seller')
        .prefetch_related('items__product')
        .annotate(
    report_profit=Sum('items__profit')).order_by('created_at')
            
        
    )
    expenses=Expense.objects.filter(date__gte=start_date, date__lte=end_date)
    total_expenses=expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_sales= sales.aggregate(total=Sum('total'))['total'] or 0
    total_profit=sales.aggregate(total=Sum('items__profit'))['total'] or 0
    total_net_profit=total_profit-total_expenses
    total_sales= sales.aggregate(total=Sum('total'))['total'] or 0
   
    total_discount= sales.aggregate(total=Sum('discount'))['total'] or 0
    transaction_count=sales.count()
    items_sold=sales.aggregate(total=Sum('items__quantity'))['total'] or 0
    report_period=(
          f"{start_date.strftime('%d %B %Y')}"
          f"-{end_date.strftime('%d %B %Y')}"

        )
    return render(
        request,
        'pos/report_detail.html',
        {
            'report_type': report_type.title,
            'report_title': report_title,
            'report_period': report_period,
            'start_date': start_date,
            'end_date': end_date,
            'total_sales': total_sales,
            'total_profit': total_profit,
            'total_discount': total_discount,
            'transaction_count': transaction_count,
            'items_sold': items_sold,
            'sales':sales,
            'total_net_profit':total_net_profit,
            'total_expenses':total_expenses,
            'generated_at': timezone.localtime(),
        }   )


#dowload pdf report
from io import BytesIO
from datetime import timedelta
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .models import Sale, Expense


@login_required
def download_report_pdf(request, report_type):
    report_type = report_type.lower()
    profile = getattr(request.user, 'profile', None)
    if profile is None or profile.role != 'OWNER':
        return redirect('sales')

    today = timezone.localdate()

    # 1. Tarehe za Kipindi (Daily, Weekly, Monthly, Yearly)
    if report_type == 'daily':
        start_date = today
        end_date = today
        report_title = 'Daily Sales Report'
    elif report_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        report_title = 'Weekly Sales Report'
    elif report_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
        report_title = 'Monthly Sales Report'
    elif report_type == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
        report_title = 'Yearly Sales Report'
    else:
        messages.error(request, 'Invalid report type')
        return redirect('reports')

    # 2. Filtering Sales & Expenses kwa Tarehe Zilizochaguliwa
    sales = Sale.objects.filter(
        sale_date__gte=start_date,
        sale_date__lte=end_date
    ).select_related('seller').prefetch_related('items__product')

    expenses = Expense.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )

    # 3. Aggregations (Total Profit & Total Net Profit)
    total_sales = sales.aggregate(total=Sum('total'))['total'] or 0
    total_profit = sales.aggregate(total=Sum('items__profit'))['total'] or 0
    total_discount = sales.aggregate(total=Sum('discount'))['total'] or 0
    transaction_count = sales.count()
    items_sold = sales.aggregate(total=Sum('items__quantity'))['total'] or 0

    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_net_profit = total_profit - total_expenses

    # 4. ReportLab PDF Setup
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    # Orange Custom Theme Styles
    orange_primary = colors.HexColor('#e65100')
    light_bg = colors.HexColor('#fff3e0')

    title_style = ParagraphStyle(
        'OrangeTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=orange_primary,
        alignment=0,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=15
    )

    story = []

    # Title & Period
    story.append(Paragraph(report_title, title_style))
    story.append(Paragraph(f"Period: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}", subtitle_style))
    story.append(Spacer(1, 10))

    # Summary Data Grid
    summary_data = [
        ['Total Sales', f"TSh {total_sales:,.2f}"],
        ['Items Sold', str(items_sold)],
        ['Transactions', str(transaction_count)],
        ['Total Discount', f"TSh {total_discount:,.2f}"],
        ['Total Expenses', f"TSh {total_expenses:,.2f}"],
        ['Total Profit', f"TSh {total_profit:,.2f}"],
        ['Total Net Profit', f"TSh {total_net_profit:,.2f}"],
        
        
       
    ]

    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#222222')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        
        # Highlight Total Expenses (Red) na Total Net Profit (Green)
        ('TEXTCOLOR', (0, 2), (1, 2), colors.HexColor('#d32f2f')),
        ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 3), (1, 3), colors.HexColor('#2e7d32')),
        ('FONTNAME', (0, 3), (1, 3), 'Helvetica-Bold'),
        
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Sales Table
    data = [
        ['Sale No.', 'Seller', 'Payment', 'Total', 'Profit', 'Date']
    ]

    for sale in sales:
        profit = sale.items.aggregate(total=Sum('profit'))['total'] or 0
        data.append([
            sale.sale_number,
            sale.seller.username if sale.seller else '-',
            sale.get_payment_method_display(),
            f"TSh {sale.total:,.2f}",
            f"TSh {profit:,.2f}",
            str(sale.sale_date)
        ])

    sales_table = Table(data, colWidths=[70, 80, 70, 90, 90, 75])
    sales_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), orange_primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ffcc80')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))

    story.append(sales_table)

    # Build PDF
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_sales_report.pdf"'
    return response

#expenses view

@login_required
def expenses(request):
  
    expenses_qs = Expense.objects.all().order_by('-date')
    today = timezone.localdate()

    if request.method == 'POST':
        title = request.POST.get('title')
        amount = request.POST.get('amount')
        category = request.POST.get('category')
        date = request.POST.get('date') or today
        description = request.POST.get('description')

        Expense.objects.create(
            title=title,
            amount=amount,
            category=category,
            date=date,
            description=description,
            created_by=request.user
        )
        return redirect('expenses')

    # Filtering Logic
    period = request.GET.get('period')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if period == 'day':
        expenses_qs = expenses_qs.filter(date=today)
    elif period == 'week':
        expenses_qs = expenses_qs.filter(date__week=today.isocalendar().week, date__year=today.year)
    elif period == 'month':
        expenses_qs = expenses_qs.filter(date__month=today.month, date__year=today.year)
    elif period == 'year':
        expenses_qs = expenses_qs.filter(date__year=today.year)

    if start_date:
        expenses_qs = expenses_qs.filter(date__gte=start_date)
    if end_date:
        expenses_qs = expenses_qs.filter(date__lte=end_date)

    total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0
    today_expenses = Expense.objects.filter(date=today).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'expenses': expenses_qs,
        'total_expenses': total_expenses,
        'today_expenses': today_expenses,
        'expenses_count': expenses_qs.count(),
    }
    return render(request, 'pos/expenses.html', context)

#loan view 
@login_required
def loans(request):

    # HANDLE FORM SUBMISSIONS
    if request.method == "POST":
        profile = getattr(request.user, 'profile', None)
        if profile is None or profile.role != 'OWNER':
                return redirect('sales')
        action = request.POST.get("action")

        # ADD NEW LOAN
        if action == "add_loan":

            customer_name = request.POST.get(
                "customer_name", ""
            ).strip()

            amount_input = request.POST.get("amount", "")

            loan_date_input = request.POST.get("loan_date", "")

            loan_date = parse_date(loan_date_input)

            if not customer_name or not amount_input or not loan_date:
                messages.error(
                    request,
                    "Please fill in all loan details."
                )
                return redirect("loans")

            try:
                amount = Decimal(amount_input)
            except (InvalidOperation, TypeError):
                messages.error(
                    request,
                    "Please enter a valid loan amount."
                )
                return redirect("loans")

            if not amount.is_finite() or amount <= Decimal("0.00"):
                messages.error(
                    request,
                    "Loan amount must be greater than zero."
                )
                return redirect("loans")

            Loan.objects.create(
                customer_name=customer_name,
                amount=amount,
                loan_date=loan_date
            )

            messages.success(
                request,
                "Loan has been added successfully!"
            )

            return redirect("loans")

        # CLEAR / DELETE LOAN AFTER PAYMENT
        elif action == "clear_loan":

            loan_id = request.POST.get("loan_id")

            loan = get_object_or_404(
                Loan,
                id=loan_id
            )

            customer_name = loan.customer_name

            # Permanently delete from database
            loan.delete()

            messages.success(
                request,
                f"{customer_name}'s loan has been cleared successfully."
            )

            return redirect("loans")

    # GET ALL LOANS
    loans_list = Loan.objects.all()

    # DATE FILTER
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None

    if date_from and not parsed_from:
        messages.error(request, "Invalid starting date.")
        date_from = ""

    if date_to and not parsed_to:
        messages.error(request, "Invalid ending date.")
        date_to = ""

    if parsed_from and parsed_to and parsed_from > parsed_to:
        messages.error(
            request,
            "Starting date cannot be later than ending date."
        )
        date_from = ""
        date_to = ""
        parsed_from = None
        parsed_to = None

    if parsed_from:
        loans_list = loans_list.filter(
            loan_date__gte=parsed_from
        )

    if parsed_to:
        loans_list = loans_list.filter(
            loan_date__lte=parsed_to
        )

    # TOTAL LOANS - ALL CURRENT DATABASE RECORDS
    total_loans = Loan.objects.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    context = {
        "loans": loans_list,
        "total_loans": total_loans,
        "date_from": date_from,
        "date_to": date_to,
    }

    return render(
        request,
        "pos/loans.html",
        context
    )

#Agency
# AGENCY CONFIGURATION


AGENCY_NETWORKS = [
    ('HALOTEL', 'Halotel'),
    ('VODACOM', 'Vodacom'),
    ('AIRTEL', 'Airtel'),
    ('YAS', 'Yas'),
]



# HELPER: GET NETWORK TOTALS


def get_network_totals(network):

    zero = Decimal('0.00')

    if not network:
        return {
            'cash': zero,
            'float': zero,
            'loans': zero,
            'total': zero,
        }

    cash = network.cash or zero
    float_amount = network.float_amount or zero
    loans = network.total_loans or zero

    return {
        'cash': cash,
        'float': float_amount,
        'loans': loans,
        'total': cash + float_amount + loans,
    }


# =====================================================
# HELPER: GENERAL REPORT TOTALS
# =====================================================

def get_report_totals(report):

    totals = {
        'cash': Decimal('0.00'),
        'float': Decimal('0.00'),
        'loans': Decimal('0.00'),
        'total': Decimal('0.00'),
    }

    for network in report.networks.all():

        values = get_network_totals(network)

        for key in totals:
            totals[key] += values[key]

    return totals


# =====================================================
# HELPER: DAILY REPORT COMPARISON
# =====================================================

def get_agency_comparison(current_report):

    previous_report = AgencyReport.objects.filter(
        seller=current_report.seller,
        report_date__lt=current_report.report_date
    ).order_by(
        '-report_date',
        '-created_at'
    ).first()

    if not previous_report:
        return None

    current_networks = {
        network.network: network
        for network in current_report.networks.all()
    }

    previous_networks = {
        network.network: network
        for network in previous_report.networks.all()
    }

    comparison_rows = []

    current_general = {
        'cash': Decimal('0.00'),
        'float': Decimal('0.00'),
        'loans': Decimal('0.00'),
        'total': Decimal('0.00'),
    }

    previous_general = {
        'cash': Decimal('0.00'),
        'float': Decimal('0.00'),
        'loans': Decimal('0.00'),
        'total': Decimal('0.00'),
    }

    for code, name in AGENCY_NETWORKS:

        current = get_network_totals(
            current_networks.get(code)
        )

        previous = get_network_totals(
            previous_networks.get(code)
        )

        difference = {
            key: current[key] - previous[key]
            for key in current
        }

        for key in current_general:
            current_general[key] += current[key]
            previous_general[key] += previous[key]

        comparison_rows.append({
            'code': code,
            'network': name,
            'current': current,
            'previous': previous,
            'difference': difference,
        })

    general_difference = {
        key: current_general[key] - previous_general[key]
        for key in current_general
    }

    return {
        'previous_report': previous_report,
        'rows': comparison_rows,
        'current_general': current_general,
        'previous_general': previous_general,
        'general_difference': general_difference,
    }



# HELPER: PERCENTAGE CHANGE


def get_percentage_change(current, previous):

    if previous == 0:

        if current > 0:
            return {
                'percentage': None,
                'label': 'NEW',
                'direction': 'up',
            }

        return {
            'percentage': Decimal('0.00'),
            'label': '0.00%',
            'direction': 'same',
        }

    percentage = (
        (current - previous) / previous
    ) * Decimal('100')

    if percentage > 0:
        direction = 'up'
    elif percentage < 0:
        direction = 'down'
    else:
        direction = 'same'

    return {
        'percentage': percentage,
        'label': f'{percentage:+.2f}%',
        'direction': direction,
    }



# AGENCY PAGE / SAVE DAILY REPORT


@login_required
def agency(request):

    if request.method == 'POST':

        try:

            report_date_string = request.POST.get('report_date')

            if not report_date_string:
                raise ValueError('Please select report date.')

            report_date = datetime.strptime(
                report_date_string,
                '%Y-%m-%d'
            ).date()

            if report_date > timezone.localdate():
                raise ValueError(
                    'Future report dates are not allowed.'
                )

            balances = {}

            # Read all four network balances
            for code, name in AGENCY_NETWORKS:

                cash = Decimal(
                    request.POST.get(
                        f'cash_{code}', '0'
                    ) or '0'
                )

                float_amount = Decimal(
                    request.POST.get(
                        f'float_{code}', '0'
                    ) or '0'
                )

                if cash < 0 or float_amount < 0:
                    raise ValueError(
                        f'{name}: Cash and Float cannot be negative.'
                    )

                balances[code] = {
                    'cash': cash,
                    'float_amount': float_amount,
                }

            # Read loan form fields
            loan_networks = request.POST.getlist('loan_network')
            borrowers = request.POST.getlist('borrower_name')
            loan_dates = request.POST.getlist('loan_date')
            loan_amounts = request.POST.getlist('loan_amount')
            loan_descriptions = request.POST.getlist(
                'loan_description'
            )

            field_lengths = {
                len(loan_networks),
                len(borrowers),
                len(loan_dates),
                len(loan_amounts),
                len(loan_descriptions),
            }

            if len(field_lengths) != 1:
                raise ValueError(
                    'Loan information is incomplete.'
                )

            loans_to_save = []

            for network, borrower, loan_date, amount, description in zip(
                loan_networks,
                borrowers,
                loan_dates,
                loan_amounts,
                loan_descriptions
            ):

                # Ignore completely empty loan rows
                if not any([
                    network,
                    borrower.strip(),
                    loan_date,
                    amount,
                    description.strip()
                ]):
                    continue

                if not all([
                    network,
                    borrower.strip(),
                    loan_date,
                    amount,
                    description.strip()
                ]):
                    raise ValueError(
                        'Complete all fields for every loan.'
                    )

                if network not in [
                    code for code, name in AGENCY_NETWORKS
                ]:
                    raise ValueError('Invalid loan network.')

                parsed_date = datetime.strptime(
                    loan_date,
                    '%Y-%m-%d'
                ).date()

                if parsed_date > report_date:
                    raise ValueError(
                        'Loan date cannot be after report date.'
                    )

                loan_amount = Decimal(amount)

                if loan_amount <= 0:
                    raise ValueError(
                        'Loan amount must be greater than zero.'
                    )

                loans_to_save.append({
                    'network': network,
                    'borrower': borrower.strip(),
                    'date': parsed_date,
                    'amount': loan_amount,
                    'description': description.strip(),
                })

            # Save report, networks and loans together
            with transaction.atomic():

                report = AgencyReport.objects.create(
                    seller=request.user,
                    report_date=report_date
                )

                saved_networks = {}

                for code, name in AGENCY_NETWORKS:

                    network_record = AgencyNetwork.objects.create(
                        report=report,
                        network=code,
                        cash=balances[code]['cash'],
                        float_amount=balances[code]['float_amount']
                    )

                    saved_networks[code] = network_record

                for loan in loans_to_save:

                    AgencyLoan.objects.create(
                        network=saved_networks[loan['network']],
                        borrower_name=loan['borrower'],
                        loan_date=loan['date'],
                        amount=loan['amount'],
                        description=loan['description']
                    )

            messages.success(
                request,
                'Agency report saved successfully!'
            )

            return redirect('agency')

        except (ValueError, InvalidOperation) as error:

            messages.error(request, str(error))

        except Exception as error:

            messages.error(
                request,
                'Something went wrong while saving the report.'
            )

    # Seller's report history
    reports = AgencyReport.objects.filter(
        seller=request.user
    ).prefetch_related(
        'networks'
    ).order_by(
        '-report_date',
        '-created_at'
    )

    latest_report = reports.first()

    comparison = None
    report_totals = None

    if latest_report:

        comparison = get_agency_comparison(latest_report)

        report_totals = get_report_totals(latest_report)

    context = {
        'networks': AGENCY_NETWORKS,
        'reports': reports,
        'today': timezone.localdate(),
        'latest_report': latest_report,
        'comparison': comparison,
        'report_totals': report_totals,
    }

    return render(
        request,
        'pos/agency.html',
        context
    )

# AGENCY PDF REPORT


@login_required
def agency_pdf(request, report_id):

    report = get_object_or_404(
        AgencyReport.objects.select_related('seller'),
        id=report_id,
        seller=request.user
    )

    network_records = report.networks.all().prefetch_related(
        'loans'
    ).order_by('network')

    # SYSTEM COLORS
    ORANGE = colors.HexColor('#FF7A00')
    DARK = colors.HexColor('#252525')
    WHITE = colors.HexColor('#FFFFFF')
    CREAM = colors.HexColor('#F8F6F1')
    GREY = colors.HexColor('#777777')
    GREEN = colors.HexColor('#16803C')
    RED = colors.HexColor('#C62828')

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=13 * mm,
        leftMargin=13 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f'Agency Report {report.report_date}',
        author='Shop System'
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'AgencyTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=23,
        leading=27,
        textColor=DARK,
        alignment=TA_CENTER,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'AgencySubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=GREY,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    heading_style = ParagraphStyle(
        'AgencyHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=DARK,
        spaceBefore=12,
        spaceAfter=8
    )

    cell_style = ParagraphStyle(
        'AgencyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=DARK
    )

    story = []

    
    # REPORT HEADER
    

    story.append(
        Paragraph('SHOP SYSTEM', title_style)
    )

    story.append(
        Paragraph(
            'AGENCY / UWAKALA FINANCIAL REPORT',
            subtitle_style
        )
    )

    seller_name = (
        report.seller.get_full_name()
        or report.seller.username
    )

    info_data = [
        [
            'SELLER',
            escape(seller_name),
            'REPORT DATE',
            str(report.report_date)
        ],
        [
            'REPORT ID',
            str(report.id),
            'GENERATED',
            str(timezone.localdate())
        ],
    ]

    info_table = Table(
        info_data,
        colWidths=[
            32 * mm,
            72 * mm,
            32 * mm,
            72 * mm
        ]
    )

    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), DARK),
        ('BACKGROUND', (2, 0), (2, -1), DARK),
        ('TEXTCOLOR', (0, 0), (0, -1), WHITE),
        ('TEXTCOLOR', (2, 0), (2, -1), WHITE),
        ('BACKGROUND', (1, 0), (1, -1), CREAM),
        ('BACKGROUND', (3, 0), (3, -1), CREAM),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))

    story.append(info_table)
    story.append(Spacer(1, 12))

    
    # NETWORK FINANCIAL SUMMARY
    

    story.append(
        Paragraph(
            'NETWORK FINANCIAL SUMMARY',
            heading_style
        )
    )

    summary_data = [[
        'NETWORK',
        'CASH (TZS)',
        'FLOAT (TZS)',
        'LOANS (TZS)',
        'NETWORK TOTAL (TZS)'
    ]]

    general = {
        'cash': Decimal('0.00'),
        'float': Decimal('0.00'),
        'loans': Decimal('0.00'),
        'total': Decimal('0.00'),
    }

    for code, name in AGENCY_NETWORKS:

        network = next(
            (
                item for item in network_records
                if item.network == code
            ),
            None
        )

        values = get_network_totals(network)

        for key in general:
            general[key] += values[key]

        summary_data.append([
            name,
            f"{values['cash']:,.2f}",
            f"{values['float']:,.2f}",
            f"{values['loans']:,.2f}",
            f"{values['total']:,.2f}",
        ])

    summary_data.append([
        'GENERAL TOTAL',
        f"{general['cash']:,.2f}",
        f"{general['float']:,.2f}",
        f"{general['loans']:,.2f}",
        f"{general['total']:,.2f}",
    ])

    summary_table = Table(
        summary_data,
        colWidths=[
            42 * mm,
            42 * mm,
            42 * mm,
            42 * mm,
            50 * mm
        ],
        repeatRows=1
    )

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('BACKGROUND', (0, 1), (-1, -2), CREAM),
        ('BACKGROUND', (0, -1), (-1, -1), ORANGE),
        ('TEXTCOLOR', (0, -1), (-1, -1), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 14))

    # =================================================
    # DAILY PERFORMANCE COMPARISON
    # =================================================

    story.append(
        Paragraph(
            'DAILY PERFORMANCE COMPARISON',
            heading_style
        )
    )

    comparison = get_agency_comparison(report)

    if comparison:

        previous_date = comparison[
            'previous_report'
        ].report_date

        story.append(
            Paragraph(
                f"Current Report: {report.report_date} "
                f"| Previous Report: {previous_date}",
                subtitle_style
            )
        )

        comparison_data = [[
            'NETWORK',
            'CURRENT TOTAL',
            'PREVIOUS TOTAL',
            'DIFFERENCE',
            'CHANGE'
        ]]

        for item in comparison['rows']:

            current = item['current']['total']
            previous = item['previous']['total']
            difference = item['difference']['total']

            change = get_percentage_change(
                current,
                previous
            )

            comparison_data.append([
                item['network'],
                f'{current:,.2f}',
                f'{previous:,.2f}',
                f'{difference:+,.2f}',
                change['label'],
            ])

        current = comparison[
            'current_general'
        ]['total']

        previous = comparison[
            'previous_general'
        ]['total']

        difference = comparison[
            'general_difference'
        ]['total']

        change = get_percentage_change(
            current,
            previous
        )

        comparison_data.append([
            'GRAND TOTAL',
            f'{current:,.2f}',
            f'{previous:,.2f}',
            f'{difference:+,.2f}',
            change['label'],
        ])

        comparison_table = Table(
            comparison_data,
            colWidths=[
                42 * mm,
                45 * mm,
                45 * mm,
                45 * mm,
                40 * mm
            ],
            repeatRows=1
        )

        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('BACKGROUND', (0, 1), (-1, -2), CREAM),
            ('BACKGROUND', (0, -1), (-1, -1), ORANGE),
            ('TEXTCOLOR', (0, -1), (-1, -1), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(comparison_table)

        
        # DETAILED GENERAL COMPARISON
        

        story.append(Spacer(1, 10))

        detail_data = [[
            'GENERAL INDICATOR',
            'CURRENT',
            'PREVIOUS',
            'DIFFERENCE'
        ]]

        for key, label in [
            ('cash', 'General Cash'),
            ('float', 'General Float'),
            ('loans', 'General Loans'),
            ('total', 'Grand Total'),
        ]:

            current_value = comparison[
                'current_general'
            ][key]

            previous_value = comparison[
                'previous_general'
            ][key]

            difference_value = comparison[
                'general_difference'
            ][key]

            detail_data.append([
                label,
                f'{current_value:,.2f}',
                f'{previous_value:,.2f}',
                f'{difference_value:+,.2f}',
            ])

        detail_table = Table(
            detail_data,
            colWidths=[
                65 * mm,
                65 * mm,
                65 * mm,
                65 * mm
            ],
            repeatRows=1
        )

        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('BACKGROUND', (0, 1), (-1, -1), CREAM),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))

        story.append(detail_table)

    else:

        story.append(
            Paragraph(
                'No previous report is available for comparison.',
                cell_style
            )
        )

    story.append(Spacer(1, 14))

    
    # INDIVIDUAL LOAN RECORDS
    

    story.append(
        Paragraph(
            'INDIVIDUAL CUSTOMER LOANS',
            heading_style
        )
    )

    loan_data = [[
        'NETWORK',
        'BORROWER NAME',
        'LOAN DATE',
        'AMOUNT (TZS)',
        'DESCRIPTION'
    ]]

    total_loan_amount = Decimal('0.00')
    loan_count = 0

    for network in network_records:

        for loan in network.loans.all():

            loan_count += 1
            total_loan_amount += loan.amount

            loan_data.append([
                network.get_network_display(),
                Paragraph(
                    escape(loan.borrower_name),
                    cell_style
                ),
                str(loan.loan_date),
                f'{loan.amount:,.2f}',
                Paragraph(
                    escape(loan.description or ''),
                    cell_style
                ),
            ])

    if loan_count == 0:

        loan_data.append([
            'NO LOANS',
            '-',
            '-',
            '0.00',
            'No customer loans recorded.'
        ])

    else:

        loan_data.append([
            'TOTAL LOANS',
            '',
            '',
            f'{total_loan_amount:,.2f}',
            ''
        ])

    loan_table = Table(
        loan_data,
        colWidths=[
            35 * mm,
            48 * mm,
            35 * mm,
            42 * mm,
            100 * mm
        ],
        repeatRows=1
    )

    loan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('BACKGROUND', (0, 1), (-1, -2), CREAM),
        ('BACKGROUND', (0, -1), (-1, -1), ORANGE),
        ('TEXTCOLOR', (0, -1), (-1, -1), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    story.append(loan_table)
    story.append(Spacer(1, 15))

    
    # GENERAL TOTAL SUMMARY


    story.append(
        Paragraph(
            'FINAL GENERAL SUMMARY',
            heading_style
        )
    )

    final_data = [
        ['GENERAL CASH', f"{general['cash']:,.2f} TZS"],
        ['GENERAL FLOAT', f"{general['float']:,.2f} TZS"],
        ['GENERAL LOANS', f"{general['loans']:,.2f} TZS"],
        ['GRAND TOTAL', f"{general['total']:,.2f} TZS"],
    ]

    final_table = Table(
        final_data,
        colWidths=[
            100 * mm,
            100 * mm
        ]
    )

    final_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), CREAM),
        ('BACKGROUND', (0, -1), (-1, -1), ORANGE),
        ('TEXTCOLOR', (0, -1), (-1, -1), WHITE),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(final_table)
    story.append(Spacer(1, 20))

    
    # FOOTER
    

    footer_style = ParagraphStyle(
        'AgencyFooter',
        parent=styles['Normal'],
        fontSize=8,
        textColor=GREY,
        alignment=TA_CENTER
    )

    story.append(
        Paragraph(
            'Generated by SHOP SYSTEM | '
            'Agency / Uwakala Management',
            footer_style
        )
    )


    # BUILD PDF
    

    document.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(
        pdf,
        content_type='application/pdf'
    )

    response[
        'Content-Disposition'
    ] = (
        f'attachment; filename="agency_report_{report.id}.pdf"'
    )

    return response
