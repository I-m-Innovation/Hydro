from django.contrib import admin

from .models import (
    TabImpianti,
    TabTipologiaTurbina,
    TabTurbinaParametri,
    tab_misuratori,
    tab_statistiche_misuratori,
    TabTurbine
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
    
@admin.register(TabTurbinaParametri)
class TabTurbinaParametriAdmin(admin.ModelAdmin):
    list_display = (
        "id_turbina",
        "eta0",
        "eta_max",
        "x0",
        "al",
        "ar",
        "kl",
        "kr",
        "q_min_ls",
        "q_max_ls",
        "metodo",
        "created_at",
        "is_active",
    )
    search_fields = ("id_turbina",)
    ordering = ("id_turbina",)

@admin.register(TabImpianti)
class TabImpiantiAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "indirizzo", "descrizione", "is_active", "created_at")
    search_fields = ("nome", "indirizzo")
    ordering = ("id",)

@admin.register(TabTurbine)
class TabTurbineAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "id_impianto",
        "id_tipologia_turbina",
        "nome",
        "salto_nominale_m",
        "salto_netto_m",
        "portata_nominale_ls",
        "portata_min_ls",
        "portata_max_ls",
        "potenza_nominale_kw",
        "rendimento_nominale",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("nome",)
    ordering = ("id",)
