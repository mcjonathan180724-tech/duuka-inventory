from multiprocessing import context

from django.shortcuts import render, get_object_or_404

from .models import Product, Sale, Supplier


# Create your views here.

def index(request):
    return render(request, 'shop/home.html')

def sales(request):
    sales_list = Sale.objects.all()
    context = {'sales_list':sales_list}
    return render(request, 'shop/sales.html', context)

def products(request):
    products_list = Product.objects.filter(
        available=True,
        quantity__gt = 0,
        is_deleted = False
    )

    context = { 'products_list': products_list }

    return render(request,'shop/products.html',context)

