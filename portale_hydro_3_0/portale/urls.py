from django.urls import path
from . import views

urlpatterns = [
    path("home/", views.home, name="home"),
    path("facilities-map/", views.facilities_map, name="facilities_map"),
    path("api/measurements/", views.measurements_api, name="measurements_api"),
    path("api/duration-curve/", views.duration_curve_api, name="duration_curve_api",),
    path("api/flow-histogram/", views.flow_histogram_api, name="flow_histogram_api",),
    path("misuratori/<str:id_misuratore>/", views.misuratore_detail, name="misuratore_detail",),
    path("api/led-status/", views.led_status_api, name="led_status_api",),
]
