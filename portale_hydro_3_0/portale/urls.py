from django.urls import path
from . import views

urlpatterns = [
    path("", views.sso_required, name="login"),
    path("login/", views.sso_required, name="login_page"),
    path("sso-login/", views.sso_login, name="sso_login"),
    path("logout/", views.logout_view, name="logout"),
    path("home/", views.misuratori_index, name="home"),
    path("facilities-map/", views.facilities_map, name="facilities_map"),
    path("api/measurements/", views.measurements_api, name="measurements_api"),
    path("api/duration-curve/", views.duration_curve_api, name="duration_curve_api",),
    path("api/flow-histogram/", views.flow_histogram_api, name="flow_histogram_api",),
    path("api/flow-histogram-hours/", views.flow_histogram_hours_api, name="flow_histogram_hours_api",),
    path("api/rendimento-potenza/", views.rendimento_potenza_api, name="rendimento_potenza_api",),
    path("api/curva-rendimento/<str:nome_turbina>/", views.curva_di_rendimento_turbina, name="curva_rendimento_api",),
    path("misuratori/", views.misuratori_index, name="misuratori_index"),
    path("misuratori/<str:id_misuratore>/", views.misuratore_detail, name="misuratore_detail",),
    path("api/led-status/", views.led_status_api, name="led_status_api",),
    path("test-canvas/<str:nome_tipologia_turbina>/", views.test_canvas, name="test_canvas",),
]
