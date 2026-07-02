from os import name

from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from datetime import date
from random import randint

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Supplier(models.Model):
    sup_ref = models.CharField(max_length=50, null=True, blank=True,)
    name = models.CharField(max_length=100, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.sup_ref:  # checks if reference is unique, not taken yet
            while True:
                rand = randint(1, 999999)
                ref = f"SUP-{rand:06d}"
                if not Supplier.objects.filter(sup_ref=ref).exists():
                    self.sup_ref = ref
                    break

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    # these product state en products type are part of Products, function called in there
    class ProductState(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        COMING = 'COMING', 'Coming'
        TAKEN = 'TAKEN', 'Taken'

    class ProductType(models.TextChoices):
        AMOLED = 'AMOLED', 'AMOLED'
        OLED = 'OLED', 'OLED'
        COPY = 'COPY', 'COPY'

#adding category for each product
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True,blank=True)
    product_ref = models.CharField(max_length=50,editable=False, blank=True)
#we set on_delete to set null, being true, meaning if a category is deleted it doesnot delete whatever belongs to it
    title = models.CharField(max_length=200)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    buying_price = models.IntegerField(validators=[MinValueValidator(1)])
    selling_price = models.IntegerField(validators=[MinValueValidator(1)])
    quantity = models.IntegerField(validators=[MinValueValidator(0)])
    
    image = models.ImageField(
        upload_to='products/',
        default='products/screenimage1.png',
        blank=True,
        null=True
    )

    type = models.CharField(
        max_length=20,
        choices=ProductType,
        default=ProductType.AMOLED
    )    #state = models.TextChoices('AVAILABLE', 'COMING', 'TAKEN')
    available = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    state = models.CharField(
        max_length=20,
        choices=ProductState,
        default=ProductState.AVAILABLE
    )
    is_deleted = models.BooleanField(default=False)

    def clean(self):
            if self.quantity < 0:
                raise ValidationError("Product quantity must be greater than 0")
            if self.buying_price <= 0:
                raise ValidationError("Product buying price must be greater than 0")
            if self.selling_price <= 0:
                raise ValidationError("Product selling price must be greater than 0")

    def save(self, *args, **kwargs):

        if not self.product_ref:  #checks if reference is unique, not taken yet
            while True:
                rand = randint(1,999999)
                ref = f"PRD-{rand:06d}"
                if not Product.objects.filter(product_ref=ref).exists():
                    self.product_ref = ref
                    break

        if self.quantity <= 0:
            self.available = False
        else:
            self.available = True

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    # low stock alert function

    @property
    def low_stock(self):
        return self.quantity > 0 and self.quantity < 3

    @property
    def out_of_stock(self):

        return self.quantity == 0

class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.IntegerField(editable=False)
    type = models.TextChoices('AMOLED', 'OLED', 'COPY')
    created = models.DateTimeField(auto_now_add=True)
    sal_ref = models.CharField(max_length=50,editable=False, blank=True)

    def __str__(self):
        return (
            f"{self.sal_ref}"
            f"{self.product.title}"
            f"{self.quantity}"
        )

    # calculating total sales
    @property
    def total_cost(self):
        return self.price * self.quantity

    # calculating total profits on each sale
    @property
    def profit(self):
        return (self.product.selling_price - self.product.buying_price) * self.quantity

    # validating sales before saving, to avoid bags
    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("You can't sell less than zero")
        elif self.quantity > self.product.quantity:
            raise ValidationError("You can't sell more than what you have")




    # now after validation you can save without bags
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.sal_ref:
            today = date.today().strftime("%Y%m%d")
            while True:
                rand = randint(100,999)
                sal = f"SAL-{today}-{rand}"
                if not Sale.objects.filter(sal_ref=sal).exists():
                    self.sal_ref = sal
                    break

        def __str__(self):
            return self.sal_ref

        if is_new:
            self.full_clean()

            # save current products price
            self.price = self.product.selling_price

            # reduce stock
            self.product.quantity -= self.quantity
            self.product.save()
            # low stock notification
            if self.product.quantity <= 3:
                Notification.objects.create(
                    product=self.product,
                    type='LOW_STOCK',
                    message=(f"{self.product.title} "
                             f"is low in stock "
                             f"({self.product.quantity} left). "
                             f"Supplier: "
                             f"{self.product.supplier}")
                )
            if self.product.quantity == 0:
                Notification.objects.create(
                    product=self.product,
                    type='OUT_OF_STOCK',
                    message=(
                        f"{self.product.title} "
                        f"is out of stock. "
                        f"Contact "
                        f"{self.product.supplier}"
                    )
                )


        super().save(*args, **kwargs)


class Restock(models.Model):
    product = models.ForeignKey( Product, on_delete=models.CASCADE )

    quantity = models.IntegerField()

    created = models.DateTimeField( auto_now_add=True )

    def __str__(self):
        return (
            f"{self.product.title} "
            f"+{self.quantity}"
        )

    def clean(self):
        if self.quantity < 0:
            raise ValidationError(
                "Restock quantity must be greater than 0"
            )

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            self.full_clean()

            # increase stock
            self.product.quantity += self.quantity
            self.product.save()

        Notification.objects.create(
            product=self.product,
            type='RESTOCK',
            message=(
                f"{self.product.title} "
                f"restocked "
                f"(+{self.quantity})"
            )
        )

        super().save(*args, **kwargs)

class Notification(models.Model):
    class notificationType(models.TextChoices):
        LOW_STOCK = 'LOW_STOCK', 'Low Stock'
        OUT_OF_STOCK = 'OUT_OF_STOCK', 'Out of Stock'
        RESTOCK = 'RESTOCK', 'Restock'
        SALE = 'SALE', 'Sale'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True,editable=False)

    message = models.TextField(editable=False)
    type = models.CharField(max_length=20, choices=notificationType.choices)
    is_read = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message

class PurchaseOrder(models.Model):
    STATUS = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('canceled', 'Canceled'),
     ]
    reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        editable=False,

    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    created = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.reference
    def save(self, *args, **kwargs):
        if not self.reference:
            today = date.today().strftime("%Y-%m-%d")
            while True:
                rand = randint(100,999)
                ref = f"{today}-{rand}"
                if not PurchaseOrder.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
        super().save(*args, **kwargs)

class PurchaseOrderItem(models.Model):
    purchaseOrder = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    def __str__(self):
        return (self.product.title)

