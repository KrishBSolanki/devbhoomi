from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, DateField
from django.db.models.functions import TruncWeek
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from bookings.models import Booking
from hotels.models import Amenity, Hotel, RoomType
from .forms import AmenityForm, HotelForm, RoomTypeForm


def staff_required(view_func):
    """Ensure only authenticated staff with at least view permission can access."""

    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access only")
        if not request.user.has_perm("hotels.view_hotel"):
            return HttpResponseForbidden("Insufficient permissions")
        return view_func(request, *args, **kwargs)

    return _wrapped


class StaffPermissionRequiredMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Mixin that also enforces is_staff for master module."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff only")
        return super().dispatch(request, *args, **kwargs)


@staff_required
def dashboard(request):
    now = timezone.now()
    today = timezone.localdate()
    week_ago = now - timedelta(days=7)
    stats = {
        "hotels": Hotel.objects.count(),
        "rooms": RoomType.objects.count(),
        "bookings": Booking.objects.count(),
        "recent_bookings": Booking.objects.filter(created_at__gte=week_ago).count(),
    }
    latest_bookings = (
        Booking.objects.select_related("hotel", "room_type")
        .order_by("-created_at")[:5]
    )
    weeks_back = 12
    current_week_start = today - timedelta(days=today.weekday())
    start_week = current_week_start - timedelta(weeks=weeks_back - 1)
    weekly_counts = (
        Booking.objects.filter(created_at__date__gte=start_week)
        .annotate(week_start=TruncWeek("created_at", output_field=DateField()))
        .values("week_start")
        .order_by("week_start")
        .annotate(total=Count("id"))
    )
    weekly_map = {entry["week_start"]: entry["total"] for entry in weekly_counts}
    chart_points = []
    for i in range(weeks_back):
        week_start = start_week + timedelta(weeks=i)
        value = weekly_map.get(week_start, 0)
        chart_points.append(
            {
                "label": week_start.strftime("%b %d"),
                "value": value,
            }
        )
    peak_value = max([point["value"] for point in chart_points] or [0])
    scale = (150 / peak_value) if peak_value else 0
    for point in chart_points:
        raw_height = point["value"] * scale if scale else 0
        if point["value"] > 0:
            point["height_px"] = max(4, int(raw_height))
        else:
            point["height_px"] = 0
    chart_data = {
        "points": chart_points,
        "range_label": "Last 12 weeks",
        "total": sum(point["value"] for point in chart_points),
        "labels": [point["label"] for point in chart_points],
        "values": [point["value"] for point in chart_points],
    }
    return render(
        request,
        "master/dashboard.html",
        {
            "stats": stats,
            "chart_data": chart_data,
            "latest_bookings": latest_bookings,
        },
    )


@method_decorator(staff_required, name="dispatch")
class HotelListView(StaffPermissionRequiredMixin, ListView):
    model = Hotel
    template_name = "master/hotels/list.html"
    context_object_name = "hotels"
    permission_required = "hotels.view_hotel"
    paginate_by = 20

    def get_queryset(self):
        queryset = Hotel.objects.all()
        search = self.request.GET.get("q")
        status = self.request.GET.get("status")
        city = self.request.GET.get("city")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(city__icontains=search)
                | Q(address__icontains=search)
            )
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        if city:
            queryset = queryset.filter(city__iexact=city)
        return queryset


@method_decorator(staff_required, name="dispatch")
class HotelCreateView(StaffPermissionRequiredMixin, CreateView):
    model = Hotel
    form_class = HotelForm
    template_name = "master/hotels/form.html"
    permission_required = "hotels.add_hotel"
    success_url = reverse_lazy("master:hotels")


@method_decorator(staff_required, name="dispatch")
class HotelUpdateView(StaffPermissionRequiredMixin, UpdateView):
    model = Hotel
    form_class = HotelForm
    template_name = "master/hotels/form.html"
    permission_required = "hotels.change_hotel"
    success_url = reverse_lazy("master:hotels")


@method_decorator(staff_required, name="dispatch")
class HotelDeleteView(StaffPermissionRequiredMixin, DeleteView):
    model = Hotel
    template_name = "master/components/confirm_delete.html"
    permission_required = "hotels.delete_hotel"
    success_url = reverse_lazy("master:hotels")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity_label"] = f"hotel '{self.object.name}'"
        context["back_url"] = reverse_lazy("master:hotels")
        return context


@method_decorator(staff_required, name="dispatch")
class RoomsHubView(StaffPermissionRequiredMixin, ListView):
    model = Hotel
    template_name = "master/rooms/hub.html"
    context_object_name = "hotels"
    permission_required = "hotels.view_roomtype"

    def get_queryset(self):
        return (
            Hotel.objects.filter(is_active=True)
            .prefetch_related("room_types")
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["room_total"] = RoomType.objects.count()
        context["hotel_total"] = Hotel.objects.count()
        return context


@method_decorator(staff_required, name="dispatch")
class RoomTypeListView(StaffPermissionRequiredMixin, ListView):
    model = RoomType
    template_name = "master/rooms/list.html"
    context_object_name = "rooms"
    permission_required = "hotels.view_roomtype"

    def get_queryset(self):
        hotel_id = self.kwargs.get("hotel_id")
        self.hotel = get_object_or_404(Hotel, pk=hotel_id)
        return RoomType.objects.filter(hotel=self.hotel)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hotel"] = self.hotel
        context["can_add_room"] = self.request.user.has_perm("hotels.add_roomtype")
        return context


@method_decorator(staff_required, name="dispatch")
class RoomTypeCreateView(StaffPermissionRequiredMixin, CreateView):
    model = RoomType
    form_class = RoomTypeForm
    template_name = "master/rooms/form.html"
    permission_required = "hotels.add_roomtype"

    def dispatch(self, request, *args, **kwargs):
        self.hotel = get_object_or_404(Hotel, pk=kwargs.get("hotel_id"))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.hotel = self.hotel
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hotel"] = self.hotel
        return context

    def get_success_url(self):
        return reverse_lazy("master:hotel-rooms", kwargs={"hotel_id": self.hotel.pk})


@method_decorator(staff_required, name="dispatch")
class RoomTypeUpdateView(StaffPermissionRequiredMixin, UpdateView):
    model = RoomType
    form_class = RoomTypeForm
    template_name = "master/rooms/form.html"
    permission_required = "hotels.change_roomtype"

    def get_success_url(self):
        return reverse_lazy("master:hotel-rooms", kwargs={"hotel_id": self.object.hotel_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hotel"] = self.object.hotel
        return context


@method_decorator(staff_required, name="dispatch")
class RoomTypeDeleteView(StaffPermissionRequiredMixin, DeleteView):
    model = RoomType
    template_name = "master/components/confirm_delete.html"
    permission_required = "hotels.delete_roomtype"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hotel"] = self.object.hotel
        context["entity_label"] = f"room type '{self.object.name}'"
        context["back_url"] = reverse_lazy(
            "master:hotel-rooms", kwargs={"hotel_id": self.object.hotel_id}
        )
        return context

    def get_success_url(self):
        return reverse_lazy("master:hotel-rooms", kwargs={"hotel_id": self.object.hotel_id})


@method_decorator(staff_required, name="dispatch")
class AmenityListView(StaffPermissionRequiredMixin, ListView):
    model = Amenity
    template_name = "master/amenities/list.html"
    context_object_name = "amenities"
    permission_required = "hotels.view_amenity"


@method_decorator(staff_required, name="dispatch")
class AmenityCreateView(StaffPermissionRequiredMixin, CreateView):
    model = Amenity
    form_class = AmenityForm
    template_name = "master/amenities/form.html"
    permission_required = "hotels.add_amenity"
    success_url = reverse_lazy("master:amenities")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Amenity"
        return context


@method_decorator(staff_required, name="dispatch")
class AmenityUpdateView(StaffPermissionRequiredMixin, UpdateView):
    model = Amenity
    form_class = AmenityForm
    template_name = "master/amenities/form.html"
    permission_required = "hotels.change_amenity"
    success_url = reverse_lazy("master:amenities")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        return context


@method_decorator(staff_required, name="dispatch")
class AmenityDeleteView(StaffPermissionRequiredMixin, DeleteView):
    model = Amenity
    template_name = "master/components/confirm_delete.html"
    permission_required = "hotels.delete_amenity"
    success_url = reverse_lazy("master:amenities")


@method_decorator(staff_required, name="dispatch")
class BookingListView(StaffPermissionRequiredMixin, ListView):
    model = Booking
    template_name = "master/bookings/list.html"
    context_object_name = "bookings"
    permission_required = "bookings.view_booking"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            Booking.objects.select_related("hotel", "room_type", "user")
            .order_by("-created_at")
        )
        status = self.request.GET.get("status")
        search = self.request.GET.get("q")
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(booking_id__icontains=search)
                | Q(hotel__name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Booking.STATUS_CHOICES
        return context
