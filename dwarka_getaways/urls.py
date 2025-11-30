"""
Main URL Configuration for dwarka_getaways project

File Location: dwarka_getaways/urls.py
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),
    
    # Core app - Homepage, About, Contact
    path('', include('core.urls')),
     # Master app - Master data management
    path('master/', include('master.urls')),
    
    # Hotels app - Search, Hotel Details
    path('hotels/', include('hotels.urls')),
    
    # Bookings app - Booking process, Confirmations
    path('bookings/', include('bookings.urls')),
    
    # Users app - Login, Signup, Profile
    path('users/', include('users.urls')),
    # Allauth social login URLs
   path('accounts/', include('allauth.urls')),
 
]

# Serve media files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)