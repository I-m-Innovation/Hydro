from datetime import timedelta
import time

from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection
from django.db.models import Max
from django.contrib.auth.decorators import login_required

from .models import tab_measurements_clean, tab_misuratori, tab_statistiche_misuratori

@login_required
def home(request):
    misuratori = tab_misuratori.objects.all()
    context = {
        "misuratori": misuratori,
        "title": "Hydro 3.0",
        "tagline": "Dashboard in arrivo",
    }
    return render(request, "portale/home.html", context)

@login_required
def facilities_map(request):
    misuratori = tab_misuratori.objects.all()
    return render(request, "portale/facilities_map.html", {
        "misuratori": misuratori,
        "title": "Facilities Map"
    })

@login_required
def measurements_api(request):
    id_misuratore = request.GET.get("id_misuratore")
    if not id_misuratore:
        return JsonResponse(
            {"error": "id_misuratore is required"},
            status=400,
        )
    range_key = request.GET.get("range", "24h")
    use_mv = range_key in {"6m", "1y", "all"}

    max_points_by_range = {
        "24h": None,
        "7d": 10000,
        "1m": 10000,
        "6m": 10000,
        "1y": 10000,
        "all": 20000,
    }
    max_points = max_points_by_range.get(range_key, 25000)

    print(
        "[measurements_api] "
        f"id={id_misuratore} range={range_key} "
        f"source={'mv_flow_daily_avg' if use_mv else 'tab_measurements_clean'}"
    )

    if use_mv:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT MAX(day)
                FROM hydro.mv_flow_daily_avg
                WHERE id_misuratore = %s
                """,
                [id_misuratore],
            )
            latest_day = cursor.fetchone()[0]

            if not latest_day:
                return JsonResponse(
                    {
                        "timestamps": [],
                        "flow_ls_raw": [],
                        "flow_ls_smoothed": [],
                        "is_outlier": [],
                    }
                )

            cutoff = None
            if range_key == "6m":
                cutoff = latest_day - timedelta(days=182)
            elif range_key == "1y":
                cutoff = latest_day - timedelta(days=365)

            if cutoff:
                cursor.execute(
                    """
                    SELECT day, flow_ls_raw_avg, flow_ls_smoothed_avg
                    FROM hydro.mv_flow_daily_avg
                    WHERE id_misuratore = %s
                      AND day >= %s
                      AND day <= %s
                    ORDER BY day
                    """,
                    [id_misuratore, cutoff, latest_day],
                )
            else:
                cursor.execute(
                    """
                    SELECT day, flow_ls_raw_avg, flow_ls_smoothed_avg
                    FROM hydro.mv_flow_daily_avg
                    WHERE id_misuratore = %s
                    ORDER BY day
                    """,
                    [id_misuratore],
                )
            rows = cursor.fetchall()

        if not rows:
            return JsonResponse(
                {
                    "timestamps": [],
                    "flow_ls_raw": [],
                    "flow_ls_smoothed": [],
                    "is_outlier": [],
                }
            )

        print(
            "[measurements_api] "
            f"id={id_misuratore} range={range_key} mv_rows={len(rows)}"
        )

        step = 1
        if max_points:
            total = len(rows)
            step = max(1, total // max_points) if total else 1

        timestamps = []
        flow_raw = []
        flow_smoothed = []
        outliers = []
        for i, (day, flow_ls_raw_avg, flow_ls_smoothed_avg) in enumerate(rows):
            if step > 1 and i % step != 0:
                continue
            timestamps.append(day.isoformat())
            flow_raw.append(
                float(flow_ls_raw_avg) if flow_ls_raw_avg is not None else None
            )
            flow_smoothed.append(
                float(flow_ls_smoothed_avg)
                if flow_ls_smoothed_avg is not None
                else None
            )
            outliers.append(None)

        data = {
            "timestamps": timestamps,
            "flow_ls_raw": flow_raw,
            "flow_ls_smoothed": flow_smoothed,
            "is_outlier": outliers,
        }
        print(
            "[measurements_api] "
            f"id={id_misuratore} range={range_key} "
            f"returned_points={len(timestamps)} step={step}"
        )
        return JsonResponse(data)
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

        if cutoff:
            rows = base_qs.filter(
                data_misurazione__gte=cutoff, data_misurazione__lte=latest
            ).order_by("data_misurazione")
        else:
            rows = base_qs.order_by("data_misurazione")


    step = 1
    if max_points:
        total = rows.count()
        if total == 0:
            return JsonResponse(
                {
                    "timestamps": [],
                    "flow_ls_raw": [],
                    "flow_ls_smoothed": [],
                    "is_outlier": [],
                }
            )
        step = max(1, total // max_points)
        print(
            "[measurements_api] "
            f"id={id_misuratore} range={range_key} raw_rows={total}"
        )
    else:
        print(
            "[measurements_api] "
            f"id={id_misuratore} range={range_key} raw_rows={rows.count()}"
        )

    timestamps = []
    flow_raw = []
    flow_smoothed = []
    outliers = []
    for i, (data_misurazione, flow_ls_raw, flow_ls_smoothed, is_outlier) in enumerate(
        rows.iterator(chunk_size=5000)
    ):
        if step > 1 and i % step != 0:
            continue
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
    print(
        "[measurements_api] "
        f"id={id_misuratore} range={range_key} "
        f"returned_points={len(timestamps)} step={step}"
    )
    return JsonResponse(data)


@login_required
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

@login_required
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

@login_required
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
    base_qs = tab_measurements_clean.objects.filter(
        id_misuratore=id_misuratore)  # qs = queryset
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

@login_required
def led_status_api(request):
    rows = (
        tab_measurements_clean.objects
        .values("id_misuratore")
        .annotate(latest_measurement=Max("data_misurazione"))
        .order_by("id_misuratore")
    )

    data = {
        "items": [
            {
                "id_misuratore": row["id_misuratore"],
                "latest_measurement": row["latest_measurement"].isoformat().replace("+00:00", "Z") if row["latest_measurement"] else None,
            }
            for row in rows
        ]
    }
    return JsonResponse(data)
