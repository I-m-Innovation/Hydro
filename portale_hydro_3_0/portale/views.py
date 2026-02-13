from datetime import timedelta
import time
import re

from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection
from django.db.models import Max
from django.contrib.auth.decorators import login_required

from .models import tab_measurements_clean, tab_misuratori, tab_statistiche_misuratori

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")
MAX_ID_MISURATORE_LEN = 128
ALLOWED_RANGE_KEYS = {"24h", "7d", "1m", "6m", "1y", "all"}


def validate_id_misuratore(raw_value):
    if raw_value is None:
        return None, "id_misuratore is required"
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)
    if len(raw_value) == 0:
        return None, "id_misuratore is required"
    if len(raw_value) > MAX_ID_MISURATORE_LEN:
        return None, f"id_misuratore is too long (max {MAX_ID_MISURATORE_LEN})"
    if CONTROL_CHARS_RE.search(raw_value):
        return None, "id_misuratore contains invalid control characters"
    if not any(not ch.isspace() for ch in raw_value):
        return None, "id_misuratore cannot be only whitespace"
    return raw_value, None

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
    id_misuratore, error = validate_id_misuratore(request.GET.get("id_misuratore"))
    if error:
        return JsonResponse({"error": error}, status=400)
    range_key = request.GET.get("range", "24h")
    if range_key not in ALLOWED_RANGE_KEYS:
        return JsonResponse(
            {
                "error": "invalid range",
                "allowed": sorted(ALLOWED_RANGE_KEYS),
            },
            status=400,
        )
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

            where_sql = "WHERE id_misuratore = %s"
            params = [id_misuratore]
            if cutoff:
                where_sql += " AND day >= %s AND day <= %s"
                params.extend([cutoff, latest_day])

            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM hydro.mv_flow_daily_avg
                {where_sql}
                """,
                params,
            )
            total = cursor.fetchone()[0] or 0
            if total == 0:
                return JsonResponse(
                    {
                        "timestamps": [],
                        "flow_ls_raw": [],
                        "flow_ls_smoothed": [],
                        "is_outlier": [],
                    }
                )

            step = 1
            if max_points:
                step = max(1, total // max_points)

            cursor.execute(
                f"""
                SELECT day, flow_ls_raw_avg, flow_ls_smoothed_avg
                FROM hydro.mv_flow_daily_avg
                {where_sql}
                ORDER BY day
                """,
                params,
            )

            timestamps = []
            flow_raw = []
            flow_smoothed = []
            outliers = []
            i = 0
            while True:
                chunk = cursor.fetchmany(5000)
                if not chunk:
                    break
                for day, flow_ls_raw_avg, flow_ls_smoothed_avg in chunk:
                    if step > 1 and i % step != 0:
                        i += 1
                        continue
                    timestamps.append(day.isoformat())
                    flow_raw.append(
                        float(flow_ls_raw_avg)
                        if flow_ls_raw_avg is not None
                        else None
                    )
                    flow_smoothed.append(
                        float(flow_ls_smoothed_avg)
                        if flow_ls_smoothed_avg is not None
                        else None
                    )
                    outliers.append(None)
                    i += 1

        data = {
            "timestamps": timestamps,
            "flow_ls_raw": flow_raw,
            "flow_ls_smoothed": flow_smoothed,
            "is_outlier": outliers,
        }
        print(
            "[measurements_api] "
            f"id={id_misuratore} range={range_key} "
            f"mv_rows={total} returned_points={len(timestamps)} step={step}"
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
    id_misuratore, error = validate_id_misuratore(request.GET.get("id_misuratore"))
    if error:
        return JsonResponse({"error": error}, status=400)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM hydro.mv_flow_exceedance_raw_vs_smoothed_2d
            WHERE id_misuratore = %s
            """,
            [id_misuratore],
        )
        total = cursor.fetchone()[0] or 0
        if total == 0:
            resp = JsonResponse(
                {
                    "exceedance_percent": [],
                    "flow_ls_smoothed": [],
                    "exceedance_percent_raw": [],
                    "flow_ls_raw": [],
                    "exceedance_percent_smoothed": [],
                }
            )
            resp["Cache-Control"] = "public, max-age=72000"  # 20 hours
            return resp

        cursor.execute(
            """
            SELECT flow_2d, p_exceed_raw, p_exceed_smoothed
            FROM hydro.mv_flow_exceedance_raw_vs_smoothed_2d
            WHERE id_misuratore = %s
            """,
            [id_misuratore],
        )
        raw_points = []
        smoothed_points = []
        while True:
            chunk = cursor.fetchmany(5000)
            if not chunk:
                break
            for flow, p_raw, p_smoothed in chunk:
                if flow is None:
                    continue
                flow_val = float(flow)
                if p_raw is not None:
                    raw_points.append((float(p_raw), flow_val))
                if p_smoothed is not None:
                    smoothed_points.append((float(p_smoothed), flow_val))

        raw_points.sort(key=lambda x: x[0])
        smoothed_points.sort(key=lambda x: x[0])

        max_points = 20000
        raw_step = max(1, len(raw_points) // max_points) if len(raw_points) > max_points else 1
        sm_step = max(1, len(smoothed_points) // max_points) if len(smoothed_points) > max_points else 1

        exceedance_raw = []
        flows_raw = []
        for i, (p, flow) in enumerate(raw_points):
            if raw_step > 1 and i % raw_step != 0:
                continue
            exceedance_raw.append(p)
            flows_raw.append(flow)

        exceedance_smoothed = []
        flows_smoothed = []
        for i, (p, flow) in enumerate(smoothed_points):
            if sm_step > 1 and i % sm_step != 0:
                continue
            exceedance_smoothed.append(p)
            flows_smoothed.append(flow)
    t1 = time.perf_counter()

    data = {
        "exceedance_percent": exceedance_smoothed,
        "flow_ls_smoothed": flows_smoothed,
        "exceedance_percent_raw": exceedance_raw,
        "flow_ls_raw": flows_raw,
        "exceedance_percent_smoothed": exceedance_smoothed,
    }
    t2 = time.perf_counter()
    print(
        "[duration_curve_api] "
        f"id={id_misuratore} rows={total} "
        f"query_ms={(t1 - t0)*1000:.1f} total_ms={(t2 - t0)*1000:.1f}"
    )
    resp = JsonResponse(data)
    resp["Cache-Control"] = "public, max-age=72000"  # 20 hours
    return resp

@login_required
def flow_histogram_api(request):
    id_misuratore, error = validate_id_misuratore(request.GET.get("id_misuratore"))
    if error:
        return JsonResponse({"error": error}, status=400)

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
    id_misuratore, error = validate_id_misuratore(id_misuratore)
    if error:
        return JsonResponse({"error": error}, status=400)
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
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id_misuratore, name, latest_measurement
            FROM hydro.mv_led_status
            ORDER BY id_misuratore
            """
        )
        rows = cursor.fetchall()

    data = {
        "items": [
            {
                "id_misuratore": row[0],
                "name": row[1],
                "latest_measurement": row[2].isoformat().replace("+00:00", "Z") if row[2] else None,
            }
            for row in rows
        ]
    }
    return JsonResponse(data)
