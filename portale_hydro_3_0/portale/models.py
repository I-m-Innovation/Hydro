from django.db import models

# Create your models here.

class tab_measurements(models.Model):
    id = models.BigAutoField(primary_key=True)
    device_id = models.TextField()
    ts_s = models.DateTimeField()
    instant_flow_rate_2 = models.FloatField(null=True)
    instant_flow_rate_1 = models.FloatField(null=True)
    fluid_velocity_2 = models.FloatField(null=True)
    fluid_velocity_1 = models.FloatField(null=True)
    instant_heat_flow_rate_2 = models.FloatField(null=True)
    instant_heat_flow_rate_1 = models.FloatField(null=True)
    return_water_temperature_2 = models.FloatField(null=True)
    return_water_temperature_1 = models.FloatField(null=True)
    supplying_water_temperature_2 = models.FloatField(null=True)
    supplying_water_temperature_1 = models.FloatField(null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "tab_measurements"
        verbose_name_plural = "Tab measurements"


class tab_measurements_clean(models.Model):
    id_misuratore = models.TextField()
    data_misurazione = models.DateTimeField()
    flow_ls_raw = models.FloatField()
    flow_ls_smoothed = models.FloatField()
    is_outlier = models.BooleanField()
    window_median = models.FloatField(null=True)
    thresholds = models.FloatField(null=True)
    
    pk = models.CompositePrimaryKey("id_misuratore", "data_misurazione")
    
    class Meta:
        managed = False
        db_table = "tab_measurements_clean"
        verbose_name_plural = "Tab measurements clean"


class tab_misuratori(models.Model):
    id_misuratore = models.TextField(primary_key=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField()
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = "tab_misuratori"
        verbose_name_plural = "Tab misuratori"


class tab_statistiche_misuratori(models.Model): 
    id_misuratore = models.TextField(primary_key=True)
    total_measurements = models.BigIntegerField()
    first_measurement = models.DateTimeField(null=True)
    last_measurement = models.DateTimeField(null=True)
    avg_24h = models.FloatField(null=True)
    avg_7d = models.FloatField(null=True)
    avg_30d = models.FloatField(null=True)
    avg_360d = models.FloatField(null=True)
    avg_all_time = models.FloatField(null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "tab_statistiche_misuratori"
        verbose_name_plural = "Tab statistiche misuratori"




class TabTipologiaTurbina(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(unique=True, max_length=50)
    descrizione = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tab_tipologia_turbina'
        verbose_name_plural = "Tab tipologia turbina"

class TabImpianti(models.Model):
    nome = models.CharField(unique=True, max_length=100)
    indirizzo = models.CharField(max_length=100, blank=True, null=True)
    descrizione = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tab_impianti'
        verbose_name_plural = "Tab impianti"

class TabTurbine(models.Model):
    id_impianto = models.ForeignKey(TabImpianti, models.DO_NOTHING, db_column='id_impianto')
    id_tipologia_turbina = models.ForeignKey(TabTipologiaTurbina, models.DO_NOTHING, db_column='id_tipologia_turbina')
    nome = models.CharField(max_length=100)
    salto_nominale_m = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    salto_netto_m = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    portata_nominale_ls = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    portata_min_ls = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    portata_max_ls = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    potenza_nominale_kw = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    rendimento_nominale = models.DecimalField(max_digits=6, decimal_places=4, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tab_turbine'
        unique_together = (('id_impianto', 'nome'),)        
        verbose_name_plural = "Tab turbine"
        
class TabTurbinaParametri(models.Model):
    id_turbina = models.OneToOneField('TabTurbine', models.DO_NOTHING, db_column='id_turbina')
    eta0 = models.DecimalField(max_digits=8, decimal_places=6)
    eta_max = models.DecimalField(max_digits=8, decimal_places=6)
    x0 = models.DecimalField(max_digits=8, decimal_places=6)
    al = models.DecimalField(max_digits=12, decimal_places=6)
    ar = models.DecimalField(max_digits=12, decimal_places=6)
    kl = models.DecimalField(max_digits=6, decimal_places=3)
    kr = models.DecimalField(max_digits=6, decimal_places=3)
    q_min_ls = models.DecimalField(max_digits=10, decimal_places=3)
    q_max_ls = models.DecimalField(max_digits=10, decimal_places=3)
    metodo = models.CharField(max_length=50, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tab_turbina_parametri'
        verbose_name_plural = "Tab turbina parametri"

