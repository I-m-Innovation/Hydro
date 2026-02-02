from datetime import timedelta
import time

from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection
from django.db.models import Max

from .models import tab_measurements_clean, tab_misuratori, tab_statistiche_misuratori


def home(request):
    misuratori = tab_misuratori.objects.all()
    context = {
        "misuratori": misuratori,
        "title": "Hydro 3.0",
        "tagline": "Dashboard in arrivo",
    }
    return render(request, "portale/home.html", context)

def facilities_map(request):
    return render(request, "portale/facilities_map.html")

def measurements_api(request):
    id_misuratore = request.GET.get("id_misuratore")
    if not id_misuratore:
        return JsonResponse(
            {"error": "id_misuratore is required"},
            status=400,
        )
    range_key = request.GET.get("range", "24h")
    base_qs = tab_measurements_clean.objects.filter(
        id_misuratore=id_misuratore
    ).values_list(
        "data_misurazione",
        "flow_ls_raw",
        "flow_ls_smoothed",
        "is_outlier",
    )
    latest = base_qs.aggregate(max_ts=Max("data_misurazione"))["max_ts"]
    rows = base_qs.none()
    if latest:
        cutoff = None
        if range_key == "24h":
            cutoff = latest - timedelta(hours=24)
        elif range_key == "7d":
            cutoff = latest - timedelta(days=7)
        elif range_key == "1m":
            cutoff = latest - timedelta(days=30)
        elif range_key == "6m":
            cutoff = latest - timedelta(days=182)
        elif range_key == "1y":
            cutoff = latest - timedelta(days=365)

        if cutoff:
            rows = base_qs.filter(
                data_misurazione__gte=cutoff, data_misurazione__lte=latest
            ).order_by("data_misurazione")
        else:
            rows = base_qs.order_by("data_misurazione")

    max_points_by_range = {
        "24h": None,
        "7d": 10000,
        "1m": 10000,
        "6m": 10000,
        "1y": 10000,
        "all": 20000,
    }
    max_points = max_points_by_range.get(range_key, 25000)
    rows_list = list(rows)
    if max_points and len(rows_list) > max_points:
        step = max(1, len(rows_list) // max_points)
        rows_list = rows_list[::step]

    timestamps = []
    flow_raw = []
    flow_smoothed = []
    outliers = []
    for data_misurazione, flow_ls_raw, flow_ls_smoothed, is_outlier in rows_list:
        timestamps.append(data_misurazione.isoformat())
        flow_raw.append(flow_ls_raw)
        flow_smoothed.append(flow_ls_smoothed)
        outliers.append(is_outlier)

    data = {
        "timestamps": timestamps,
        "flow_ls_raw": flow_raw,
        "flow_ls_smoothed": flow_smoothed,
        "is_outlier": outliers,
    }
    return JsonResponse(data)

def duration_curve_api(request):
    t0 = time.perf_counter()
    id_misuratore = request.GET.get("id_misuratore")
    if not id_misuratore:
        return JsonResponse(
            {"error": "id_misuratore is required"},
            status=400,
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT flow_avg_day, p_exceed
            FROM hydro.mv_flow_duration_curve_daily
            WHERE id_misuratore = %s
            ORDER BY p_exceed
            """,
            [id_misuratore],
        )
        rows = cursor.fetchall()
    t1 = time.perf_counter()

    total = len(rows)
    if total == 0:
        return JsonResponse({"exceedance_percent": [], "flow_ls_smoothed": []})

    max_points = 20000
    if total > max_points:
        step = max(1, total // max_points)
        rows = rows[::step]

    flows = [float(flow) for flow, _p in rows]
    exceedance = [float(p) for _flow, p in rows]

    data = {
        "exceedance_percent": exceedance,
        "flow_ls_smoothed": flows,
    }
    t2 = time.perf_counter()
    print(
        "[duration_curve_api] "
        f"id={id_misuratore} rows={total} "
        f"query_ms={(t1 - t0)*1000:.1f} total_ms={(t2 - t0)*1000:.1f}"
    )
    return JsonResponse(data)

def flow_histogram_api(request):
    id_misuratore = request.GET.get("id_misuratore")
    if not id_misuratore:
        return JsonResponse(
            {"error": "id_misuratore is required"},
            status=400,
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH latest AS (
                SELECT MAX(updated_at) AS updated_at
                FROM hydro.tab_flow_histogram
                WHERE id_misuratore = %s
            )
            SELECT bin_index, range_start, range_end, count
            FROM hydro.tab_flow_histogram
            WHERE id_misuratore = %s
              AND updated_at = (SELECT updated_at FROM latest)
            ORDER BY bin_index
            """,
            [id_misuratore, id_misuratore],
        )
        rows = cursor.fetchall()

    if not rows:
        return JsonResponse(
            {
                "bin_index": [],
                "range_start": [],
                "range_end": [],
                "count": [],
            }
        )

    bin_index = [int(row[0]) for row in rows]
    range_start = [float(row[1]) for row in rows]
    range_end = [float(row[2]) for row in rows]
    counts = [int(row[3]) for row in rows]
    total = sum(counts)
    percents = [
        (count / total * 100) if total > 0 else 0.0
        for count in counts
    ]

    return JsonResponse(
        {
            "bin_index": bin_index,
            "range_start": range_start,
            "range_end": range_end,
            "count": counts,
            "percent": percents,
        }
    )

def misuratore_detail(request, id_misuratore):
    misuratore = (
        tab_misuratori.objects.filter(id_misuratore=id_misuratore)
        .only(
            "id_misuratore",
            "name",
            "location",
            "latitude",
            "longitude",
            "created_at",
            "is_active",
        )
        .first()
    )
    misuratore_stats = (
        tab_statistiche_misuratori.objects.filter(
            id_misuratore=id_misuratore
        ).first()
    )
    if misuratore:
        name = misuratore.name
    else:
        name = "Unknown Misuratore"
    
    misuratori = tab_misuratori.objects.only(
        "id_misuratore",
        "name",
        "is_active",
    )
    base_qs = tab_measurements_clean.objects.filter(id_misuratore=id_misuratore) # qs = queryset
    latest = base_qs.aggregate(max_ts=Max("data_misurazione"))["max_ts"]  
    misurazioni = base_qs.none()



    if latest:
        cutoff = latest - timedelta(hours=24)
        misurazioni = base_qs.filter(
            data_misurazione__gte=cutoff, data_misurazione__lte=latest
        ).order_by("data_misurazione")
    
    
    
    
    context = {
        "title": f"Misuratore {name}",
        "misuratori": misuratori,
        "misuratore": misuratore,
        "misurazioni": misurazioni,
        "misuratore_stats": misuratore_stats,
    }
    return render(request, "portale/misuratore_detail.html", context)

def led_status_api(request):
    rows = (
        tab_measurements_clean.objects
        .values("id_misuratore")
        .annotate(latest_measurement=Max("data_misurazione"))
        .order_by("id_misuratore")
    )
    
    data = {
        "items" : [
            {
            "id_misuratore": row["id_misuratore"],
            "latest_measurement": row["latest_measurement"].isoformat().replace("+00:00", "Z") if row["latest_measurement"] else None,
            } 
        for row in rows
        ]
    }
    return JsonResponse(data)