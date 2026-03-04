from django.contrib import admin

from .models import (
    TabTipologiaTurbina,
    tab_measurements,
    tab_measurements_clean,
    tab_misuratori,
    tab_statistiche_misuratori,
)


@admin.register(tab_misuratori)
class TabMisuratoriAdmin(admin.ModelAdmin):
    list_display = (
        "id_misuratore",
        "name",
        "location",
        "latitude",
        "longitude",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("id_misuratore", "name", "location")
    ordering = ("id_misuratore",)


@admin.register(tab_statistiche_misuratori)
class TabStatisticheMisuratoriAdmin(admin.ModelAdmin):
    list_display = (
        "id_misuratore",
        "total_measurements",
        "first_measurement",
        "last_measurement",
        "avg_24h",
        "avg_7d",
        "avg_30d",
        "avg_360d",
        "avg_all_time",
        "updated_at",
    )
    search_fields = ("id_misuratore",)
    ordering = ("id_misuratore",)


@admin.register(TabTipologiaTurbina)
class TabTipologiaTurbinaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "descrizione")
    search_fields = ("nome",)
    ordering = ("id",)
    
        
        
