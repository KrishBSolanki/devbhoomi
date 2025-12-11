"""Bookings app views"""

from datetime import datetime
import logging
import warnings

warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API",
    category=UserWarning,
    module="razorpay.client",
)

import razorpay
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Booking, GuestDetail, Payment, Coupon
from hotels.models import Hotel, RoomType


logger = logging.getLogger(__name__)


def _get_razorpay_client():
    """Return configured Razorpay client or raise ValueError"""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay credentials are not configured")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def booking_page(request, hotel_slug, room_type_id=None):
    """Booking page for a specific hotel"""
    hotel = get_object_or_404(Hotel, slug=hotel_slug, is_active=True)
    razorpay_enabled = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)

    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # Determine selected room type
    room_queryset = hotel.room_types.filter(is_available=True)
    room_type = None
    if room_type_id:
        room_type = get_object_or_404(room_queryset, id=room_type_id)
    else:
        room_type_param = request.GET.get('room')
        if room_type_param:
            room_type = room_queryset.filter(id=room_type_param).first()
    room_type = room_type or room_queryset.first()

    recent_search = request.session.get('recent_search', {})

    # Capture child age selections
    child_age_items = sorted(
        [
            (key, value)
            for key, value in request.GET.items()
            if key.startswith('child_age_') and value not in (None, '')
        ],
        key=lambda item: int(''.join(filter(str.isdigit, item[0])) or 0)
    )

    def _safe_age(value):
        try:
            age = int(value)
            return age if 0 <= age <= 17 else None
        except (TypeError, ValueError):
            return None

    child_age_values = [age for _, value in child_age_items if (age := _safe_age(value)) is not None]
    if not child_age_values:
        recent_child_ages = recent_search.get('child_ages') or []
        child_age_values = [
            age for age in recent_child_ages
            if isinstance(age, int) and 0 <= age <= 17
        ]

    # Get search parameters from query params or fallback to recent search/session
    checkin = request.GET.get('checkin') or request.GET.get('checkIn') or recent_search.get('checkin', '')
    checkout = request.GET.get('checkout') or request.GET.get('checkOut') or recent_search.get('checkout', '')
    adults = _safe_int(request.GET.get('adults'), _safe_int(recent_search.get('adults'), 2))
    children = _safe_int(request.GET.get('children'), _safe_int(recent_search.get('children'), 0))
    rooms = _safe_int(request.GET.get('rooms'), _safe_int(recent_search.get('rooms'), 1))
    total_guests = _safe_int(request.GET.get('guests'), _safe_int(recent_search.get('guests'), adults + children))
    search_location = request.GET.get('location') or recent_search.get('location') or hotel.name

    # Calculate nights
    nights = 0
    checkin_date = checkout_date = None
    if checkin and checkout:
        try:
            checkin_date = datetime.strptime(checkin, '%Y-%m-%d').date()
            checkout_date = datetime.strptime(checkout, '%Y-%m-%d').date()
            nights = max((checkout_date - checkin_date).days, 1)
        except ValueError:
            checkin_date = checkout_date = None

    # Calculate pricing using hotel's base rate so edits reflect everywhere
    nightly_rate = float(hotel.base_price)
    stay_nights = nights or 1
    base_price = nightly_rate * stay_nights * rooms
    discount = (base_price * hotel.discount_percentage) / 100 if hotel.discount_percentage else 0
    coupon_discount = 0  # Placeholder to be updated when coupon applied
    subtotal = base_price - discount - coupon_discount
    taxes = subtotal * 0.12  # 12% GST
    total = subtotal + taxes

    amenities = hotel.amenities.all()
    food_info = getattr(hotel, 'food_info', None)
    rules_info = getattr(hotel, 'rules', None)
    default_food = [
        "Complimentary breakfast buffet",
        "Pure vegetarian kitchen",
        "24/7 room service",
    ]
    default_rules = [
        "Check-in after 12:00 PM",
        "Valid ID proof required for all guests",
        "No smoking inside rooms",
    ]

    context = {
        'hotel': hotel,
        'selected_room': room_type,
        'room_types': room_queryset,
        'checkin': checkin,
        'checkout': checkout,
        'checkin_date': checkin_date,
        'checkout_date': checkout_date,
        'adults': adults,
        'children': children,
        'rooms': rooms,
        'total_guests': total_guests,
        'child_ages': child_age_values,
        'search_location': search_location,
        'nights': stay_nights,
        'pricing': {
            'nightly_rate': nightly_rate,
            'base_price': base_price,
            'discount': discount,
            'coupon_discount': coupon_discount,
            'taxes': taxes,
            'total': total,
        },
        'booking_summary': {
            'nights': stay_nights,
            'rooms': rooms,
            'guests_label': f"{adults} Adults" + (f" & {children} Children" if children else ''),
        },
        'amenities': amenities,
        'food_info': food_info or default_food,
        'rules_info': rules_info or default_rules,
        'booking_form_action': reverse('bookings:process'),
        'razorpay_enabled': razorpay_enabled,
        'login_url': reverse('users:login'),
        'signup_url': reverse('users:signup'),
    }

    return render(request, 'bookings/booking_page.html', context)


from django.contrib.auth.decorators import login_required

@login_required(login_url='users:login')
def process_booking(request):
    """Process booking form submission"""
    if request.method == 'POST':
        # Get form data
        hotel_id = request.POST.get('hotel_id')
        room_type_id = request.POST.get('room_type_id')
        checkin = request.POST.get('checkin')
        checkout = request.POST.get('checkout')
        adults = request.POST.get('adults')
        children = request.POST.get('children')
        rooms = request.POST.get('rooms')

        # Guest details
        title = request.POST.get('title')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        id_type = request.POST.get('id_type')
        id_number = request.POST.get('id_number')
        special_requests = request.POST.get('special_requests', '')

        # Payment method
        payment_method = request.POST.get('payment_method', 'razorpay')
        valid_methods = [choice[0] for choice in Payment.PAYMENT_METHODS]
        if payment_method not in valid_methods:
            payment_method = 'razorpay'

        # Coupon
        coupon_code = request.POST.get('coupon_code', '').strip()

        try:
            hotel = Hotel.objects.get(id=hotel_id)
            room_type = RoomType.objects.get(id=room_type_id)
            booking_page_url = reverse('bookings:booking_page', kwargs={'hotel_slug': hotel.slug})
            booking_page_with_room = f"{booking_page_url}?room={room_type.id}" if room_type else booking_page_url

            rooms_count = max(int(rooms or 1), 1)
            adults_count = max(int(adults or 1), 1)
            children_count = max(int(children or 0), 0)

            if not checkin or not checkout:
                messages.error(request, 'Please complete the booking details (dates & rooms) before filling guest information.')
                return redirect(booking_page_with_room)

            try:
                checkin_date = datetime.strptime(checkin, '%Y-%m-%d').date()
                checkout_date = datetime.strptime(checkout, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid check-in or check-out date. Please re-enter your stay details.')
                return redirect(booking_page_with_room)

            nights = max((checkout_date - checkin_date).days, 1)

            # Calculate pricing based on hotel's base rate to keep consistency with listings
            nightly_rate = float(hotel.base_price)
            base_price = nightly_rate * nights * rooms_count
            discount_rate = float(hotel.discount_percentage or 0)
            discount_amount = (base_price * discount_rate) / 100 if discount_rate else 0

            coupon_discount = 0
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code=coupon_code.upper())
                    if coupon.is_valid():
                        if coupon.discount_type == 'percentage':
                            coupon_discount = (base_price * coupon.discount_value) / 100
                            if coupon.max_discount:
                                coupon_discount = min(coupon_discount, float(coupon.max_discount))
                        else:
                            coupon_discount = float(coupon.discount_value)
                        coupon.used_count += 1
                        coupon.save()
                except Coupon.DoesNotExist:
                    messages.warning(request, 'Coupon code is invalid or expired.')

            subtotal = base_price - discount_amount - coupon_discount
            taxes = max(subtotal * 0.12, 0)
            total_amount = subtotal + taxes

            requires_online_payment = payment_method == 'razorpay'
            if requires_online_payment and (not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET):
                messages.error(request, 'Online payments are temporarily unavailable. Please choose Pay at Hotel.')
                return redirect(booking_page_with_room)

            booking = Booking.objects.create(
                user=request.user if request.user.is_authenticated else None,
                hotel=hotel,
                room_type=room_type,
                check_in=checkin_date,
                check_out=checkout_date,
                nights=nights,
                num_adults=adults_count,
                num_children=children_count,
                num_rooms=rooms_count,
                base_price=base_price,
                discount_amount=discount_amount,
                taxes=taxes,
                total_amount=total_amount,
                coupon_code=coupon_code,
                coupon_discount=coupon_discount,
                special_requests=special_requests,
                status='confirmed' if payment_method == 'payathotel' else 'pending',
                payment_status='pending'
            )

            GuestDetail.objects.create(
                booking=booking,
                title=title,
                full_name=full_name,
                email=email,
                phone=phone,
                id_type=id_type,
                id_number=id_number
            )

            payment = Payment.objects.create(
                booking=booking,
                payment_method=payment_method,
                amount=total_amount,
                is_successful=False
            )

            if payment_method == 'payathotel':
                messages.success(request, f'Booking confirmed! Your booking ID is {booking.booking_id}. Please pay at the hotel.')
                return redirect('bookings:confirmation', booking_id=booking.booking_id)

            try:
                client = _get_razorpay_client()
                amount_paise = int(float(total_amount) * 100)
                order = client.order.create(data={
                    'amount': amount_paise,
                    'currency': settings.RAZORPAY_DEFAULT_CURRENCY,
                    'receipt': booking.booking_id,
                    'notes': {
                        'hotel': hotel.name,
                        'guest': full_name,
                        'booking_id': booking.booking_id,
                    },
                })
                payment.gateway_order_id = order.get('id', '')
                payment.save(update_fields=['gateway_order_id'])

                context = {
                    'booking': booking,
                    'hotel': hotel,
                    'order_id': order.get('id'),
                    'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                    'amount_paise': amount_paise,
                    'display_amount': total_amount,
                    'currency': settings.RAZORPAY_DEFAULT_CURRENCY,
                    'verify_url': reverse('bookings:verify_payment'),
                    'guest': {
                        'name': full_name,
                        'email': email,
                        'phone': phone,
                    },
                    'cancel_url': booking_page_with_room,
                }
                return render(request, 'bookings/razorpay_checkout.html', context)
            except Exception as exc:
                booking.status = 'cancelled'
                booking.payment_status = 'failed'
                booking.save(update_fields=['status', 'payment_status'])
                payment.remarks = f'Razorpay order creation failed: {exc}'
                payment.save(update_fields=['remarks'])
                logger.exception("Razorpay order creation failed for booking %s", booking.booking_id)
                messages.error(request, 'Unable to initiate online payment. Please try again or choose Pay at Hotel.')
                return redirect(booking_page_with_room)

        except Exception as e:
            logger.exception("Booking processing failed. POST data: %s", request.POST.dict())
            messages.error(request, f'Booking failed: {str(e)}')
            return redirect('hotels:search')

    return redirect('hotels:search')


@require_POST
def verify_razorpay_payment(request):
    """Verify Razorpay payment signature and finalize booking"""
    booking_id = request.POST.get('booking_id')
    order_id = request.POST.get('razorpay_order_id')
    payment_id = request.POST.get('razorpay_payment_id')
    signature = request.POST.get('razorpay_signature')

    booking = get_object_or_404(Booking, booking_id=booking_id)
    payment = getattr(booking, 'payment', None)
    if not payment or payment.payment_method != 'razorpay':
        messages.error(request, 'Invalid payment attempt.')
        return redirect('bookings:booking_page', hotel_slug=booking.hotel.slug)

    if not all([order_id, payment_id, signature]):
        messages.error(request, 'Incomplete payment details received. Please try again.')
        return redirect('bookings:booking_page', hotel_slug=booking.hotel.slug)

    try:
        client = _get_razorpay_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
    except razorpay.errors.SignatureVerificationError:
        payment.gateway_order_id = order_id
        payment.gateway_payment_id = payment_id
        payment.gateway_signature = signature
        payment.remarks = 'Signature verification failed'
        payment.save(update_fields=['gateway_order_id', 'gateway_payment_id', 'gateway_signature', 'remarks'])
        booking.payment_status = 'failed'
        booking.save(update_fields=['payment_status'])
        messages.error(request, 'Payment verification failed. No amount was captured.')
        return redirect('bookings:booking_page', hotel_slug=booking.hotel.slug)
    except ValueError:
        messages.error(request, 'Online payments are unavailable. Please try again later.')
        return redirect('bookings:booking_page', hotel_slug=booking.hotel.slug)

    payment.transaction_id = payment_id
    payment.gateway_order_id = order_id
    payment.gateway_payment_id = payment_id
    payment.gateway_signature = signature
    payment.is_successful = True
    payment.payment_date = timezone.now()
    payment.save(update_fields=[
        'transaction_id',
        'gateway_order_id',
        'gateway_payment_id',
        'gateway_signature',
        'is_successful',
        'payment_date',
    ])

    booking.payment_status = 'paid'
    booking.status = 'confirmed'
    booking.save(update_fields=['payment_status', 'status'])

    messages.success(request, f'Payment successful! Booking ID {booking.booking_id} is confirmed.')
    return redirect('bookings:confirmation', booking_id=booking.booking_id)


def booking_confirmation(request, booking_id):
    """Booking confirmation page"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    context = {
        'booking': booking,
    }
    
    return render(request, 'bookings/confirmation.html', context)


def my_bookings(request):
    """User's booking history"""
    if not request.user.is_authenticated:
        return redirect('users:login')
    
    bookings = Booking.objects.filter(user=request.user)
    
    context = {
        'bookings': bookings,
    }
    
    return render(request, 'bookings/my_bookings.html', context)

