"""
Hotels app views - Search, Details, Filters
"""

import re

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.urls import reverse

from .models import Hotel, Amenity, Review

def search_hotels(request):
    """Hotel search results with filters"""
    
    # Get search parameters
    location = request.GET.get('location', 'Dwarka, Gujarat')
    checkin = request.GET.get('checkin', '')
    checkout = request.GET.get('checkout', '')
    guests = request.GET.get('guests', '2')
    
    # Get filter parameters
    min_price = request.GET.get('min_price', 500)
    max_price = request.GET.get('max_price', 10000)
    star_ratings = request.GET.getlist('star_rating')
    property_types = request.GET.getlist('property_type')
    amenities = request.GET.getlist('amenity')
    
    # Sort parameter
    sort_by = request.GET.get('sort', 'recommended')
    
    # Base queryset
    hotels = Hotel.objects.filter(is_active=True)
    
    # Apply price filter
    try:
        min_price = float(min_price)
        max_price = float(max_price)
        hotels = hotels.filter(
            base_price__gte=min_price,
            base_price__lte=max_price
        )
    except (ValueError, TypeError):
        pass
    
    # Apply star rating filter
    if star_ratings:
        hotels = hotels.filter(star_rating__in=star_ratings)
    
    # Apply property type filter
    if property_types:
        hotels = hotels.filter(property_type__in=property_types)
    
    # Apply amenity filter
    if amenities:
        for amenity_id in amenities:
            hotels = hotels.filter(amenities__id=amenity_id)
    
    # Apply sorting
    if sort_by == 'price_low':
        hotels = hotels.order_by('base_price')
    elif sort_by == 'price_high':
        hotels = hotels.order_by('-base_price')
    elif sort_by == 'rating':
        hotels = hotels.order_by('-rating')
    elif sort_by == 'distance':
        # You can implement custom distance sorting
        pass
    else:  # recommended
        hotels = hotels.order_by('-is_featured', '-rating')
    
    default_image = "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=300&h=250&fit=crop"
    hotel_cards = []
    for idx, hotel in enumerate(hotels, start=1):
        distance_label = hotel.distance_from_temple or "Dwarka"
        match = re.search(r"[\d.]+", distance_label)
        distance_value = float(match.group()) if match else 0

        amenities_list = []
        features = []

        if hotel.has_wifi:
            amenities_list.append('wifi')
            features.append({"icon": "fas fa-wifi", "label": "Free Wi-Fi"})
        if hotel.has_breakfast:
            amenities_list.append('breakfast')
            features.append({"icon": "fas fa-coffee", "label": "Breakfast"})
        if hotel.has_temple_view:
            amenities_list.append('templeview')
            features.append({"icon": "fas fa-om", "label": "Temple View"})
        if hotel.has_parking:
            amenities_list.append('parking')
            features.append({"icon": "fas fa-parking", "label": "Parking"})
        if hotel.has_ac:
            amenities_list.append('ac')
            features.append({"icon": "fas fa-snowflake", "label": "AC Rooms"})

        discount_label = f"{hotel.discount_percentage}% OFF" if hotel.discount_percentage else ""

        detail_link = reverse('hotels:details', args=[hotel.slug])
        booking_link = reverse('bookings:booking_page', args=[hotel.slug])

        hotel_cards.append({
            "id": hotel.slug,
            "name": hotel.name,
            "badge": hotel.badge or "",
            "rating": float(hotel.rating or 0),
            "reviews": hotel.total_reviews or 0,
            "distance": distance_value,
            "distanceLabel": distance_label,
            "description": (hotel.description or "")[:200],
            "price": float(hotel.discounted_price or 0),
            "originalPrice": float(hotel.base_price or 0),
            "discountLabel": discount_label,
            "img": hotel.main_image.url if getattr(hotel.main_image, 'url', None) else default_image,
            "link": detail_link,
            "bookingLink": booking_link,
            "propertyType": hotel.property_type,
            "amenities": amenities_list,
            "features": features,
            "order": idx,
        })

    # Get all amenities for filter display
    all_amenities = Amenity.objects.all()
    
    context = {
        'hotels': hotels,
        'hotels_count': hotels.count(),
        'all_amenities': all_amenities,
        'hotel_cards': hotel_cards,
        'search_params': {
            'location': location,
            'checkin': checkin,
            'checkout': checkout,
            'guests': guests,
        },
        'filters': {
            'min_price': min_price,
            'max_price': max_price,
            'star_ratings': star_ratings,
            'property_types': property_types,
            'amenities': amenities,
            'sort_by': sort_by,
        }
    }
    
    return render(request, 'search/search.html', context)


def hotel_details(request, slug):
    """Hotel details page"""
    hotel = get_object_or_404(
        Hotel.objects.prefetch_related('images', 'amenities', 'room_types'),
        slug=slug,
        is_active=True,
    )
    reviews = Review.objects.filter(hotel=hotel, is_approved=True)[:10]
    room_types = hotel.room_types.filter(is_available=True)
    related_hotels = Hotel.objects.filter(is_active=True).exclude(id=hotel.id)[:3]
    gallery_images = hotel.images.all()
    amenities = hotel.amenities.all()
    booking_url = reverse('bookings:booking_page', args=[hotel.slug])
    
    context = {
        'hotel': hotel,
        'reviews': reviews,
        'room_types': room_types,
        'related_hotels': related_hotels,
        'gallery_images': gallery_images,
        'amenities': amenities,
        'booking_url': booking_url,
    }
    
    return render(request, 'hotels/hotel_details.html', context)

