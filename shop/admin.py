import string
from multiprocessing import context

from django import urls
from django.contrib import admin
from django.core.mail import message
from django.db.models import Model
from django.template.defaultfilters import title
from django.utils.html import format_html
from django.views.generic import detail
from django.urls import path
from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, Sale, Restock, Category, Supplier, Notification, PurchaseOrderItem, PurchaseOrder
from .views import sales
from django.contrib.admin import AdminSite, action
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.contrib.admin import AdminSite
from django.utils import timezone


def dashboard_stats(request):

    today = timezone.now().date()

    return {
        'product_count': Product.objects.filter(
            is_deleted=False,
            available = True
        ).count(),

        'sales_count': Sale.objects.count(),

        'sales_today': Sale.objects.filter(
            created__date=today
        ).count(),

        'low_stock': Product.objects.filter(
            quantity__lt=2
        ).count(),

        'inactive_product': Product.objects.filter(
            available=False
        ).count(),
        'deleted_product': Product.objects.filter(is_deleted=True).count(),
    }


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name','phone','email','location','created',)
    search_fields = ('name','phone','email',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name','created',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'product_image',
        'view_product',
        'category',
        'supplier',
        'quantity',
        'selling_price',
        'available',
        'low_stock_status',

        'quick_actions',

    )
    list_display_links = None
    list_per_page = 5


    @admin.action(description="Restore selected products")
    def restore_products(
            self,
            request,
            queryset
    ):
        queryset.update(
            is_deleted=False
        )

    actions =['restore_products']

    # list_display=('product_image','view_product','quantity', 'selling_price')

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [

            path(
                'deleted/',
                self.admin_site.admin_view(
                    self.deleted_products
                ),
                name='deleted_products'
            ),

            path(
                '<int:product_id>/restore/',
                self.admin_site.admin_view(
                    self.restore_product
                ),
                name='restore_product'
            ),

            path(
                '<int:product_id>/detail/',
                self.admin_site.admin_view(
                    self.product_details
                ),
                name='product_details'
            ),
        ]

        return custom_urls + urls

    def restore_product(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)

        product.is_deleted= False
        product.save()

        return redirect('/admin/shop/product/deleted/'
)

    def deleted_products(
            self,
            request
    ):
        deleted_items = Product.objects.filter(
            is_deleted=True
        )

        context = {
            **self.admin_site.each_context(
                request
            ),
            'title': 'Deleted Products',
            'products': deleted_items,
        }

        return render(
            request,
            'admin/deleted_products.html',
            context
        )
#adding button at top

    change_list_template = ('admin/product_change_list.html')

    def delete_model(self, request, obj):
        obj.is_deleted = True
        obj.save()



    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_deleted=False)

    exclude = ('is_deleted',)

    @admin.action(description="Archive selected products")
    def archive_products(self, request, queryset):

        queryset.update(
            is_deleted=True
        )

    @admin.action(description="Restore selected products")
    def restore_products(self, request, queryset):

        queryset.update(
            is_deleted=False
        )

    actions = [
        'archive_products',
        'restore_products'
    ]


    def view_product(self, obj):
        detail_url = (
            f"/admin/shop/product/{obj.id}/detail/"
        )
        return format_html('<a href="{}">{}</a>',
                           detail_url,
                           obj.title
                           )
    view_product.short_description = 'Title'

    def has_delete_permission(
            self,
            request,
            obj=None
    ):

        return False


    def product_details(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        context = {**self.admin_site.each_context(request),'product':product, **dashboard_stats(request)}

        return render(request, 'admin/product_details.html', context)

    def product_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="40" height="40" style="border-radius:8px;">', obj.image.url)
        return "No Image"
    product_image.short_description = 'Image'

 # Right sidebar filters

    search_fields = ('title', 'description', )

    list_filter = ('available','created','is_deleted')

    ordering = ('-created',)

    list_editable = ('available',)

    # adding category filter
    list_filter = ('category', 'available', 'created')



    def low_stock_status(self, obj):
        if obj.low_stock:
            return "⚠️ Low Stock"
        elif obj.out_of_stock:
            return "❌ Out of Stock"
        return "✅ In Stock"

    low_stock_status.short_description = 'Stock Status'

    class Media:
        css = {
            'all': (

                'admin/custom_admin.css',
            )
        }

    def quick_actions(self, obj):
        edit_url = (
            f"/admin/shop/product/{obj.id}/change/"
        )

        sale_url = (
            f"/admin/shop/sale/add/?product={obj.id}"
        )

        restock_url = (
            f"/admin/shop/restock/add/?product={obj.id}"
        )

        details_url = (
            f"/admin/shop/product/{obj.id}/detail/"
        )


        return format_html(
            """
            <div class="dropdown">
                <button type="button" class="dropbtn">
                    ⋮ More
                </button>

                <div class="dropdown-content">
                    <a href="{}">✏️ Edit</a>
                    <a href="{}">💰 Sale</a>
                    <a href="{}">📦 Restock</a>
                    <a href="{}">👁 View Details</a>
                </div>
            </div>
            """,
            edit_url,
            sale_url,
            restock_url,
            details_url,
        )

    quick_actions.short_description = (
        "Actions"
    )

# class for making a sale

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):

    # function to filter out only non deleted products en available stock only

    def formfield_for_foreignkey(
            self,
            db_field,
            request,
            **kwargs
    ):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(
                is_deleted = False,
                available = True
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    list_display = (
        'view_sales',
        'quantity',
        'price',
        'total_cost',
        'profit',
        'created',

    )

    # this below line makes title clikable disabled.
    list_display_links = None

    def view_sales(self, obj):
        detail_url = ( f"/admin/shop/sale/{obj.id}/detail/")
        return format_html('<a href="{}">{}</a>',detail_url, obj.product.title)
    view_sales.short_description = 'Sale'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [ path('<int:sale_id>/detail/', self.admin_site.admin_view(self.sale_details),
                 name='sale_details'),]
        return custom_urls + urls

    def sale_details(self, request, sale_id):
        sale = get_object_or_404(Sale, pk=sale_id)
        context = {**self.admin_site.each_context(request), 'sale':sale, **dashboard_stats(request)}
        return render(request, 'admin/sale_details.html', context)

    search_fields = (
        'product__title',
    )

    ordering = (
        '-created',
    )

# class for making a restock

@admin.register(Restock)
class RestockAdmin(admin.ModelAdmin):

    # function to filter out only non deleted products en available stock only

    def formfield_for_foreignkey(
            self,
            db_field,
            request,
            **kwargs
    ):

        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(
                is_deleted=False
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    list_display = (
        'product',
        'quantity',
        'created',
    )

    readonly_fields = (
        'product',
        'quantity',
        'created',
    )
    list_display_links = None

    def has_delete_permission(
            self,
            request,
            obj= None
    ):
        return False

    def has_add_permission(
        self,
        request
    ):
        return True

    def has_change_permission(
            self,
            request,
            obj=None
    ):
        # allow opening page
        if obj:
            return True

        return super().has_change_permission(
            request,
            obj
        )

    def get_readonly_fields(
            self,
            request,
            obj=None
    ):
        # existing restock history
        if obj:
            return (
                'product',
                'quantity',
                'created',
            )

        # new restock creation
        return (
            'created',
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'view_message',
        'type',
        'read_status',
        'created'
    )

    ordering = ('-created',)
    list_display_links = None

    class Media:
        js = ('admin/notification.js',)

# making a popup for the notifications
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [path('<int:notification_id>/popup/',
                            self.admin_site.admin_view(self.notification_popup),
                            name='notification_popup'),
                       path('report/', self.admin_site.admin_view(self.reports), name='reports')

                       ]
        return custom_urls + urls

    def notification_popup(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id)

        #mark as read automatically
        if not notification.is_read:

            notification.is_read = True
            notification.save()
        product = notification.product

        return JsonResponse({
            'message': notification.message,
            'type': notification.type,
            'product': (product.title if product else 'No product'),
            'quantity':(product.quantity if product else 0),
            'supplier':(str(product.supplier) if product and product.supplier else 'No supplier'),
            'restock_url':(f"/admin/shop/restock/add/?product={product.id}" if product else "#")
        })

    def view_message(self, obj):
        return format_html(
            '''
        <a href="#"
           class="notification-link"
           data-id="{}">
            {}
        </a>
        ''',
        obj.id,
        obj.message
        )
    view_message.short_description = 'Message'

    def read_status(self, obj):

        if obj.is_read:
            return "✅ Read"

        return "🔴 Unread"

    read_status.short_description = (
        "Status"
    )

    def reports(self, request):
        sales = Sale.objects.all()
        revenue = sum(sale.total_cost for sale in sales)
        profit = sum(sale.profit for sale in sales)
        top_product = (Sale.objects.values('product__title').annotate(sold=Sum('quantity')).order_by('-sold')[:5])
        context = {
            **self.admin_site.each_context(request),
            'revenue': revenue,
            'profit': profit,
            'top_product': top_product,
        }

        return render(request, 'admin/reports.html', context)

class ReportAdmin:
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [path('report/', self.admin_site.admin_view(self.reports), name='report'),]
        return custom_urls + urls

class MyAdminSite(AdminSite):

    site_header = "My Duuka Admin"
    site_title = "Duuka Dashboard"
    index_title = "Inventory System"

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [

            path(
                'reports/',
                self.admin_view(
                    self.reports
                ),
                name='reports'
            ),

            path(
                'reports/low-stock/',
                self.admin_view(
                    self.low_stock_report
                ),
                name='low_stock_report'
            ),

            path(
                'reports/out-of-stock/',
                self.admin_view(
                    self.out_of_stock_report
                ),
                name='out_of_stock_report'
            ),

            path(
                'reports/inactive/',
                self.admin_view(
                    self.inactive_report
                ),
                name='inactive_report'
            ),

            path('reports/suppliers/',
                 self.admin_view(self.supplier_report
                ),
                 name='supplier_report'
                 ),

            path(
                'reports/supplier/<int:supplier_id>/',
                self.admin_view(self.supplier_details_report),
                name='supplier_detail'
            ),

        ]

        return custom_urls + urls
    from django.db.models import Sum

    def supplier_details_report(self, request, supplier_id):
        supplier = get_object_or_404(Supplier, pk=supplier_id)
        products = Product.objects.filter(supplier=supplier, is_deleted=False)
        low_stock = products.filter(quantity__gt=0, quantity__lt =3).count()
        out_of_stock = products.filter(quantity__gt=0).count()
        total_stock = sum(p.quantity for p in products)
        context = {
            **self.each_context(request),
            'supplier': supplier,
            'products': products,
            'total_stock': total_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,

        }
        return render(request, 'admin/supplier_detail.html', context)

    def reports(self, request):

        sales = Sale.objects.all()

        revenue = sum(sale.total_cost for sale in sales )

        profit = sum( sale.profit for sale in sales )

        top_products = ( Sale.objects

            .values('product__title')

            .annotate( sold=Sum('quantity')

            )

            .order_by('-sold' )[:5]

        )
        stock = Product.objects.filter(is_deleted=False).count()
        low_stock = Product.objects.filter(quantity__gt = 0, quantity__lt = 3).count()
        out_of_stock = Product.objects.filter(quantity = 0).count()
        inactive = Product.objects.filter(available=False).count()
        deleted = Product.objects.filter(is_deleted=True).count()

        context = {

            **self.each_context(

                request

            ),

            'revenue': f"{revenue:,}",

            'profit': f"{profit:,}",

            'top_products': top_products,
            'stock': stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'inactive': inactive,
            'deleted': deleted,

        }

        return render(request,'admin/reports.html', context )


    def each_context(self, request):

        context = super().each_context(request)

        today = timezone.now().date()

        context.update({
            'product_count': Product.objects.filter(is_deleted=False).count(),

            'sales_count': Sale.objects.count(),

            'sales_today': Sale.objects.filter(
                created__date=today
            ).count(),

            'low_stock': Product.objects.filter(
                quantity__gt=0,
                quantity__lt=3
            ).count(),

            'out_of_stock': Product.objects.filter(quantity = 0, ),

            'inactive_product': Product.objects.filter(
                available=False
            ).count(),
            'deleted_product': Product.objects.filter(is_deleted=True).count(),

            'reports_url': '/admin/reports/',

        })

        return context


    def low_stock_report(self, request):

        products = Product.objects.filter(

            quantity__gt=0,

            quantity__lt=3,

            is_deleted=False

        )

        context = {

            **self.each_context(request),

            'title': 'Low Stock',

            'products': products

        }

        return render(

            request,

            'admin/report_products.html',

            context

        )


    def out_of_stock_report(self, request):

        products = Product.objects.filter(

            quantity=0,


        )

        context = {

            **self.each_context(request),

            'title': 'Out Of Stock',

            'products': products

        }

        return render(

            request,

            'admin/report_products.html',

            context

        )

    def inactive_report(self, request):
        products = Product.objects.filter(
            available=False
        )

        context = {
            **self.each_context(request),
            'title': 'Inactive Products',
            'products': products
        }

        return render(
            request,
            'admin/report_products.html',
            context
        )

    def supplier_report (self, request):
        suppliers = Supplier.objects.all()
        context = {
            **self.each_context(request),
            'title': 'Suppliers',
            'suppliers': suppliers
        }
        return render(
            request, 'admin/supplier_report.html', context
        )

class PurchaseOrderItemInLine(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1

    def formfield_for_foreignkey(
            self,
            db_field,
            request,
            **kwargs
    ):

        if db_field.name == "product":

            object_id = request.resolver_match.kwargs.get("object_id")

            if object_id:

                po = PurchaseOrder.objects.get(pk=object_id)

                kwargs["queryset"] = Product.objects.filter(
                    supplier=po.supplier,
                    is_deleted=False
                )

            else:

                supplier = request.GET.get("supplier")

                if supplier:
                    kwargs["queryset"] = Product.objects.filter(
                        supplier_id=supplier,
                        is_deleted=False
                    )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'supplier', 'status', 'created')
    inlines = [PurchaseOrderItemInLine]



    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        suppliers = request.GET.get('supplier')
        if suppliers:
            initial['supplier'] = suppliers

        return initial

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('supplier',)

        return ()

    
    def response_change(self, request, obj):

        if "_send" in request.POST:

            obj.status = "sent"

            obj.save()

            self.message_user(

                request,

                "Purchase Order sent."

            )

        elif "_draft" in request.POST:

            obj.status = "draft"

            obj.save()

        return super().response_change(request, obj)

admin.site.__class__ = MyAdminSite

admin.site.site_header = "My Duuka Admin"
admin.site.site_title = "Duuka Dashboard"
admin.site.index_title = "Inventory System"