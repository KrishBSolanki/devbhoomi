from django.urls import path

from . import views

app_name = "master"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("hotels/", views.HotelListView.as_view(), name="hotels"),
    path("hotels/create/", views.HotelCreateView.as_view(), name="hotel-create"),
    path("hotels/<int:pk>/edit/", views.HotelUpdateView.as_view(), name="hotel-edit"),
    path("hotels/<int:pk>/delete/", views.HotelDeleteView.as_view(), name="hotel-delete"),
    path("rooms/", views.RoomsHubView.as_view(), name="rooms-hub"),
    path(
        "hotels/<int:hotel_id>/rooms/",
        views.RoomTypeListView.as_view(),
        name="hotel-rooms",
    ),
    path(
        "hotels/<int:hotel_id>/rooms/create/",
        views.RoomTypeCreateView.as_view(),
        name="room-create",
    ),
    path("rooms/<int:pk>/edit/", views.RoomTypeUpdateView.as_view(), name="room-edit"),
    path("rooms/<int:pk>/delete/", views.RoomTypeDeleteView.as_view(), name="room-delete"),
    path("amenities/", views.AmenityListView.as_view(), name="amenities"),
    path("amenities/create/", views.AmenityCreateView.as_view(), name="amenity-create"),
    path("amenities/<int:pk>/edit/", views.AmenityUpdateView.as_view(), name="amenity-edit"),
    path("amenities/<int:pk>/delete/", views.AmenityDeleteView.as_view(), name="amenity-delete"),
    path("bookings/", views.BookingListView.as_view(), name="bookings"),
]
