"""Hotels app views - Search, Details, Filters"""

import re
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from .models import Amenity, Hotel, Review


LOCATION_LABEL_TO_ZONE = {
    "Dwarkadhish Temple, Dwarka, Gujarat": "dwarkadhish",
    "Gomti Ghat, Dwarka, Gujarat": "gomti_ghat",
    "Dwarka Beach, Dwarka, Gujarat": "dwarka_beach",
    "Bet Dwarka, Dwarka, Gujarat": "bet_dwarka",
}

def search_hotels(request):
    """Hotel search results with filters"""

    # Get search parameters
    location = request.GET.get('location', 'Dwarka, Gujarat')
    checkin = request.GET.get('checkin') or request.GET.get('checkIn') or ''
    checkout = request.GET.get('checkout') or request.GET.get('checkOut') or ''
    guests = request.GET.get('guests', '2')
    adults = request.GET.get('adults', '2')
    children = request.GET.get('children', '0')
    rooms = request.GET.get('rooms', '1')

    def _parse_child_age(value):
        try:
            age = int(value)
            return age if 0 <= age <= 17 else None
        except (TypeError, ValueError):
            return None

    child_age_items = sorted(
        [
            (key, value)
            for key, value in request.GET.items()
            if key.startswith('child_age_') and value not in (None, '')
        ],
        key=lambda item: int(''.join(filter(str.isdigit, item[0])) or 0)
    )
    child_age_params = {key: value for key, value in child_age_items}
    child_age_values = [
        age for _, value in child_age_items
        if (age := _parse_child_age(value)) is not None
    ]

    search_params = {
        'location': location,
        'checkin': checkin,
        'checkout': checkout,
        'guests': guests,
        'adults': adults,
        'children': children,
        'rooms': rooms,
    }
    
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

    zone = LOCATION_LABEL_TO_ZONE.get(location)
    if zone:
        hotels = hotels.filter(location_zone=zone)
    
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
    query_dict = {k: v for k, v in search_params.items() if v}
    query_dict.update(child_age_params)
    search_query = urlencode(query_dict)

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

        hotel_detail_link = reverse('hotels:details', args=[hotel.slug])
        if search_query:
            hotel_detail_link = f"{hotel_detail_link}?{search_query}"

        try:
            image_url = hotel.main_image.url
        except (ValueError, AttributeError):
            image_url = default_image

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
            "img": image_url,
            "link": hotel_detail_link,
            "propertyType": hotel.property_type,
            "amenities": amenities_list,
            "features": features,
            "order": idx,
        })

    paginator = Paginator(hotel_cards, 1)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_hotels = page_obj.object_list

    preserved_query_params = request.GET.copy()
    preserved_query_params.pop('page', None)
    pagination_querystring = preserved_query_params.urlencode()
    page_base_url = f"?{pagination_querystring}&" if pagination_querystring else "?"

    # Get all amenities for filter display
    all_amenities = Amenity.objects.all()
    
    recent_search = {
        **search_params,
        'child_ages': child_age_values,
    }

    # Persist recent search in session for later pages (hotel details / booking)
    request.session['recent_search'] = recent_search

    context = {
        'hotels': hotels,
        'hotels_count': paginator.count,
        'all_amenities': all_amenities,
        'hotel_cards': hotel_cards,
        'page_obj': page_obj,
        'page_hotels': page_hotels,
        'page_base_url': page_base_url,
        'search_params': search_params,
        'child_ages': child_age_values,
        'search_query': search_query,
        'filters': {
            'min_price': min_price,
            'max_price': max_price,
            'star_ratings': star_ratings,
            'property_types': property_types,
            'amenities': amenities,
            'sort_by': sort_by,
        },
        'pagination_querystring': pagination_querystring,
    }
    
    return render(request, 'search/search.html', context)


def hotel_details(request, slug):
    """Hotel details page"""
    hotel = get_object_or_404(Hotel, slug=slug, is_active=True)
    recent_search = request.session.get('recent_search', {})

    def _parse_child_age(value):
        try:
            age = int(value)
            return age if 0 <= age <= 17 else None
        except (TypeError, ValueError):
            return None

    child_age_items = sorted(
        [
            (key, value)
            for key, value in request.GET.items()
            if key.startswith('child_age_') and value not in (None, '')
        ],
        key=lambda item: int(''.join(filter(str.isdigit, item[0])) or 0)
    )
    child_age_params = {}
    child_age_values = []
    for key, value in child_age_items:
        age = _parse_child_age(value)
        if age is not None:
            child_age_values.append(age)
            child_age_params[key] = str(age)
    if not child_age_params and recent_search.get('child_ages'):
        for idx, age in enumerate(recent_search.get('child_ages'), start=1):
            if isinstance(age, int) and 0 <= age <= 17:
                child_age_values.append(age)
                child_age_params[f'child_age_{idx}'] = str(age)

    def _get_param(key, fallback=''):
        return request.GET.get(key) or recent_search.get(key, fallback)

    search_params = {
        'location': request.GET.get('location') or recent_search.get('location') or hotel.name,
        'checkin': request.GET.get('checkin') or request.GET.get('checkIn') or recent_search.get('checkin', ''),
        'checkout': request.GET.get('checkout') or request.GET.get('checkOut') or recent_search.get('checkout', ''),
        'guests': request.GET.get('guests') or recent_search.get('guests', ''),
        'adults': request.GET.get('adults') or recent_search.get('adults', ''),
        'children': request.GET.get('children') or recent_search.get('children', ''),
        'rooms': request.GET.get('rooms') or recent_search.get('rooms', ''),
    }
    query_dict = {k: v for k, v in search_params.items() if v not in (None, '')}
    query_dict.update(child_age_params)

    # Handle review submission
    if request.method == 'POST':
        from django.shortcuts import redirect

        delete_review_id = request.POST.get('delete_review_id')
        if delete_review_id:
            review = Review.objects.filter(id=delete_review_id, hotel=hotel).first()
            if review:
                if request.user.is_authenticated and (review.author == request.user or request.user.is_staff):
                    review.delete()
                    messages.success(request, 'Review deleted.')
                else:
                    messages.error(request, 'You are not allowed to delete this review.')
            return redirect(request.path)

        edit_review_id = request.POST.get('edit_review_id')
        if edit_review_id:
            review = Review.objects.filter(id=edit_review_id, hotel=hotel).first()
            if review:
                if request.user.is_authenticated and (review.author == request.user or request.user.is_staff):
                    review.rating = int(request.POST.get('edit_rating'))
                    review.comment = request.POST.get('edit_comment')
                    review.stay_date = request.POST.get('edit_stay_date')
                    review.save(update_fields=["rating", "comment", "stay_date"])
                    messages.success(request, 'Review updated.')
                else:
                    messages.error(request, 'You are not allowed to edit this review.')
            return redirect(request.path)
        guest_name = request.POST.get('guest_name')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        stay_date = request.POST.get('stay_date')
        if guest_name and rating and comment and stay_date:
            Review.objects.create(
                hotel=hotel,
                guest_name=guest_name,
                rating=int(rating),
                comment=comment,
                stay_date=stay_date,
                is_approved=True,
                author=request.user if request.user.is_authenticated else None,
            )
            messages.success(request, 'Thank you for your review!')
            return redirect(request.path)

    all_reviews = Review.objects.filter(hotel=hotel, is_approved=True)
    reviews = all_reviews[:10]
    room_types = hotel.room_types.filter(is_available=True)
    related_hotels = Hotel.objects.filter(
        is_active=True
    ).exclude(id=hotel.id)[:3]
    gallery_images = hotel.images.all()
    amenities = hotel.amenities.all()
    from django.urls import reverse
    booking_base = reverse('bookings:booking_page', args=[hotel.slug])
    booking_url = f"{booking_base}?{urlencode(query_dict)}" if query_dict else booking_base

    # Calculate dynamic average rating and update hotel.rating
    if all_reviews.exists():
        dynamic_rating = round(sum(r.rating for r in all_reviews) / all_reviews.count(), 2)
        if hotel.rating != dynamic_rating:
            hotel.rating = dynamic_rating
            hotel.total_reviews = all_reviews.count()
            hotel.save(update_fields=["rating", "total_reviews"])
    else:
        dynamic_rating = None
        if hotel.rating != 0:
            hotel.rating = 0
            hotel.total_reviews = 0
            hotel.save(update_fields=["rating", "total_reviews"])

    context = {
        'hotel': hotel,
        'reviews': reviews,
        'room_types': room_types,
        'related_hotels': related_hotels,
        'gallery_images': gallery_images,
        'amenities': amenities,
        'booking_url': booking_url,
        'search_params': search_params,
        'child_ages': child_age_values,
        'dynamic_rating': dynamic_rating,
        'all_reviews': all_reviews,
    }
    
    return render(request, 'hotels/hotel_details.html', context)

