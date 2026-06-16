from datetime import timedelta
from bisect import bisect_right
from urllib.parse import urlencode
import time
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.db import connection
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from .models import tab_measurements_clean, tab_misuratori, tab_statistiche_misuratori

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")
MAX_ID_MISURATORE_LEN = 128
ALLOWED_RANGE_KEYS = {"24h", "7d", "1m", "6m", "1y", "all"}
EXPECTED_POWER_RANGES = set(ALLOWED_RANGE_KEYS)
WATER_DENSITY_KG_M3 = 1000.0
GRAVITY_M_S2 = 9.81


def _portale_home_url():
    return reverse("misuratori_index")


def _safe_local_redirect(request, raw_target, fallback):
    target = str(raw_target or "").strip()
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return fallback


def _redirect_to_eyeq_entry(request, *, message=""):
    entry_url = str(getattr(settings, "EYEQ_PORTALE_IMPIANTI_ENTRY_URL", "") or "").strip()
    if not entry_url:
        raise PermissionDenied("Accesso consentito solo tramite Eye-Q.")
    if message:
        messages.error(request, message)

    next_path = _safe_local_redirect(request, request.GET.get("next"), _portale_home_url())
    separator = "&" if "?" in entry_url else "?"
    return redirect(f"{entry_url}{separator}{urlencode({'next': next_path})}")


@never_cache
def sso_required(request):
    if request.user.is_authenticated:
        return redirect("misuratori_index")
    return _redirect_to_eyeq_entry(request)


def _load_sso_payload(token):
    shared_secret = str(getattr(settings, "EYEQ_PORTALE_IMPIANTI_SSO_SECRET", "") or "")
    if not shared_secret:
        raise PermissionDenied("SSO Portale Impianti non configurato.")

    return signing.loads(
        token,
        key=shared_secret,
        salt=str(
            getattr(settings, "EYEQ_PORTALE_IMPIANTI_SSO_SALT", "eyeq-portale-impianti-sso")
            or "eyeq-portale-impianti-sso"
        ),
        max_age=int(getattr(settings, "EYEQ_PORTALE_IMPIANTI_SSO_MAX_AGE_SECONDS", 60) or 60),
    )


def _payload_has_value(value, expected):
    if isinstance(value, (list, tuple, set)):
        return expected in {str(item or "").strip() for item in value}
    return str(value or "").strip() == expected


def _validate_sso_authorization(payload):
    expected_issuer = str(getattr(settings, "EYEQ_PORTALE_IMPIANTI_SSO_ISSUER", "eyeq") or "eyeq").strip()
    expected_audience = str(
        getattr(settings, "EYEQ_PORTALE_IMPIANTI_SSO_AUDIENCE", "portale_impianti") or "portale_impianti"
    ).strip()

    if str(payload.get("iss") or "").strip() != expected_issuer:
        raise PermissionDenied("Issuer SSO non valido.")
    if not _payload_has_value(payload.get("aud"), expected_audience):
        raise PermissionDenied("Token SSO non destinato a Portale Impianti.")
    if not _payload_has_value(payload.get("page"), expected_audience):
        raise PermissionDenied("Utente non autorizzato da Eye-Q per Portale Impianti.")


def _sso_user_from_payload(payload):
    username = str(payload.get("username") or payload.get("sub") or "").strip()[:150]
    if not username:
        raise PermissionDenied("Token SSO senza utente.")

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()

    user.email = str(payload.get("email") or user.email or "").strip()[:254]
    user.first_name = str(payload.get("first_name") or user.first_name or "").strip()[:150]
    user.last_name = str(payload.get("last_name") or user.last_name or "").strip()[:150]
    user.is_active = True
    user.save()
    return user


@never_cache
def sso_login(request):
    token = str(request.GET.get("token") or "").strip()
    if not token:
        return _redirect_to_eyeq_entry(request, message="Accesso a Portale Impianti consentito solo da Eye-Q.")

    try:
        payload = _load_sso_payload(token)
    except signing.SignatureExpired:
        return _redirect_to_eyeq_entry(request, message="Accesso scaduto. Riapri Portale Impianti da Eye-Q.")
    except signing.BadSignature:
        return _redirect_to_eyeq_entry(request, message="Accesso non valido. Riapri Portale Impianti da Eye-Q.")

    _validate_sso_authorization(payload)
    user = _sso_user_from_payload(payload)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    next_url = _safe_local_redirect(request, payload.get("next") or request.GET.get("next"), _portale_home_url())
    return redirect(next_url)


def logout_view(request):
    logout(request)
    return redirect("login")


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


def _safe_float(value):
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _pick_flow_ls(flow_ls_raw, flow_ls_smoothed):
    """
    Use smoothed flow when present, otherwise fallback to raw flow.
    """
    flow = _safe_float(flow_ls_smoothed)
    if flow is not None:
        return flow
    return _safe_float(flow_ls_raw)


def _get_turbina_curve_points_by_id(id_turbina):
    """
    Returns two sorted arrays (q_points_ls, eta_points) from tab_turbina_curve_points.
    Points with null q_ls or null eta are skipped.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT q_ls, eta
            FROM hydro.tab_turbina_curve_points
            WHERE id_turbina = %s
            AND q_ls IS NOT NULL
            AND eta IS NOT NULL
            ORDER BY q_ls ASC
            """,
            [id_turbina],
        )
        rows = cursor.fetchall()

    q_points_ls = []
    eta_points = []
    for q_ls, eta in rows:
        q_val = _safe_float(q_ls)
        eta_val = _safe_float(eta)
        if q_val is None or eta_val is None:
            continue
        q_points_ls.append(q_val)
        eta_points.append(eta_val)
    return q_points_ls, eta_points


def _interpolate_eta_linear_clamped(flow_ls, q_points_ls, eta_points):
    """
    Linear interpolation with clamp:
    - below first q -> first eta
    - above last q -> last eta
    """
    if flow_ls is None or not q_points_ls or not eta_points:
        return None
    if len(q_points_ls) == 1:
        return eta_points[0]

    if flow_ls <= q_points_ls[0]:
        return eta_points[0]
    if flow_ls >= q_points_ls[-1]:
        return eta_points[-1]

    right_idx = bisect_right(q_points_ls, flow_ls)
    left_idx = right_idx - 1
    q0 = q_points_ls[left_idx]
    q1 = q_points_ls[right_idx]
    eta0 = eta_points[left_idx]
    eta1 = eta_points[right_idx]

    if q1 <= q0:
        return eta0
    ratio = (flow_ls - q0) / (q1 - q0)
    return eta0 + (eta1 - eta0) * ratio


def _compute_expected_power_kw(flow_ls, head_m, eta):
    """
    P[kW] = rho * g * Q[m3/s] * H[m] * eta / 1000
    where Q[m3/s] = flow_ls / 1000.
    """
    if flow_ls is None or head_m is None or eta is None:
        return None
    if head_m <= 0:
        return None
    if flow_ls <= 0:
        return 0.0
    q_m3s = flow_ls / 1000.0
    power_kw = (WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * q_m3s * head_m * eta) / 1000.0
    return round(max(0.0, power_kw), 2)

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
    should_compute_expected_power = range_key in EXPECTED_POWER_RANGES
    expected_setup = None
    if should_compute_expected_power:
        expected_setup = _get_expected_power_config_for_misuratore(id_misuratore)
        if not expected_setup:
            print(
                "[measurements_api] "
                f"id={id_misuratore} range={range_key} expected_power=disabled (missing config)"
            )

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
                        "expected_power_kw": [],
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
                        "expected_power_kw": [],
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
            expected_power = []
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
                    if expected_setup:
                        flow_used = _pick_flow_ls(flow_ls_raw_avg, flow_ls_smoothed_avg)
                        eta = _interpolate_eta_linear_clamped(
                            flow_used,
                            expected_setup["q_points_ls"],
                            expected_setup["eta_points"],
                        )
                        expected_power.append(
                            _compute_expected_power_kw(
                                flow_used,
                                expected_setup["head_m"],
                                eta,
                            )
                        )
                    else:
                        expected_power.append(None)
                    i += 1

        data = {
            "timestamps": timestamps,
            "flow_ls_raw": flow_raw,
            "flow_ls_smoothed": flow_smoothed,
            "is_outlier": outliers,
            "expected_power_kw": expected_power,
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
                    "expected_power_kw": [],
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
    expected_power = []
    for i, (data_misurazione, flow_ls_raw, flow_ls_smoothed, is_outlier) in enumerate(
        rows.iterator(chunk_size=5000)
    ):
        if step > 1 and i % step != 0:
            continue
        timestamps.append(data_misurazione.isoformat())
        flow_raw.append(flow_ls_raw)
        flow_smoothed.append(flow_ls_smoothed)
        outliers.append(is_outlier)
        if expected_setup:
            flow_used = _pick_flow_ls(flow_ls_raw, flow_ls_smoothed)
            eta = _interpolate_eta_linear_clamped(
                flow_used,
                expected_setup["q_points_ls"],
                expected_setup["eta_points"],
            )
            expected_power.append(
                _compute_expected_power_kw(
                    flow_used,
                    expected_setup["head_m"],
                    eta,
                )
            )
        else:
            expected_power.append(None)

    data = {
        "timestamps": timestamps,
        "flow_ls_raw": flow_raw,
        "flow_ls_smoothed": flow_smoothed,
        "is_outlier": outliers,
        "expected_power_kw": expected_power,
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
            FROM hydro.mv_flow_duration_curve_hourly_raw_local
            WHERE id_misuratore = %s
            """,
            [id_misuratore],
        )
        total = cursor.fetchone()[0] or 0
        if total == 0:
            resp = JsonResponse(
                {
                    "exceedance_percent": [],
                    "flow_ls_raw": [],
                }
            )
            resp["Cache-Control"] = "public, max-age=72000"  # 20 hours
            return resp

        cursor.execute(
            """
            SELECT flow_avg_hour_raw, p_exceed
            FROM hydro.mv_flow_duration_curve_hourly_raw_local
            WHERE id_misuratore = %s
            ORDER BY p_exceed
            """,
            [id_misuratore],
        )
        points = []
        while True:
            chunk = cursor.fetchmany(5000)
            if not chunk:
                break
            for flow, p_exceed in chunk:
                if flow is None:
                    continue
                flow_val = float(flow)
                if p_exceed is not None:
                    points.append((float(p_exceed), flow_val))

        max_points = 20000
        step = max(1, len(points) // max_points) if len(points) > max_points else 1

        exceedance = []
        flows_raw = []
        for i, (p, flow) in enumerate(points):
            if step > 1 and i % step != 0:
                continue
            exceedance.append(p)
            flows_raw.append(flow)
    t1 = time.perf_counter()

    data = {
        "exceedance_percent": exceedance,
        "flow_ls_raw": flows_raw,
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
def flow_histogram_hours_api(request):
    id_misuratore, error = validate_id_misuratore(request.GET.get("id_misuratore"))
    if error:
        return JsonResponse({"error": error}, status=400)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                bin_index,
                range_start,
                range_end,
                hours_raw,
                hours_smoothed,
                updated_at
            FROM hydro.mv_flow_histogram_hours
            WHERE id_misuratore = %s
            ORDER BY bin_index
            """,
            [id_misuratore],
        )
        rows = cursor.fetchall()

    if not rows:
        return JsonResponse(
            {
                "bin_index": [],
                "range_start": [],
                "range_end": [],
                "hours_raw": [],
                "hours_smoothed": [],
                "updated_at": None,
            }
        )

    bin_index = [int(row[0]) for row in rows]
    range_start = [float(row[1]) for row in rows]
    range_end = [float(row[2]) for row in rows]
    hours_raw = [int(row[3]) for row in rows]
    hours_smoothed = [int(row[4]) for row in rows]
    latest_updated_at = max((row[5] for row in rows if row[5] is not None), default=None)

    return JsonResponse(
        {
            "bin_index": bin_index,
            "range_start": range_start,
            "range_end": range_end,
            "hours_raw": hours_raw,
            "hours_smoothed": hours_smoothed,
            "updated_at": latest_updated_at.isoformat() if latest_updated_at else None,
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


def _get_latest_flow_avg_30m(id_misuratore):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MAX(data_misurazione)
            FROM hydro.tab_measurements_clean
            WHERE id_misuratore = %s
            """,
            [id_misuratore],
        )
        latest_ts = cursor.fetchone()[0]
        if not latest_ts:
            return None, None

        cutoff = latest_ts - timedelta(minutes=30)
        cursor.execute(
            """
            SELECT AVG(flow_ls_smoothed)
            FROM hydro.tab_measurements_clean
            WHERE id_misuratore = %s
                AND data_misurazione >= %s
                AND data_misurazione <= %s
            """,
            [id_misuratore, cutoff, latest_ts],
        )
        flow_ls_avg = cursor.fetchone()[0]

    return latest_ts, flow_ls_avg


def _get_turbina_params_for_misuratore(id_misuratore):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT name
            FROM hydro.tab_misuratori
            WHERE id_misuratore = %s
            """,
            [id_misuratore],
        )
        row = cursor.fetchone()
        if not row:
            return None

        impianto_name = row[0]
        cursor.execute(
            """
            SELECT  t.id,
                    t.salto_netto_m,
                    t.salto_nominale_m,
                    p.eta0,
                    p.eta_max,
                    p.x0,
                    p.aL,
                    p.aR,
                    p.kL,
                    p.kR,
                    p.q_min_ls,
                    p.q_max_ls
            FROM hydro.tab_turbine t
            JOIN hydro.tab_impianti i ON i.id = t.id_impianto
            JOIN hydro.tab_turbina_parametri p ON p.id_turbina = t.id
            WHERE i.nome = %s
            AND p.is_active = TRUE
            ORDER BY t.id
            LIMIT 1
            """,
            [impianto_name],
        )
        return cursor.fetchone()


def _get_expected_power_config_for_misuratore(id_misuratore):
    """
    Resolve runtime configuration for expected power from DB:
    - turbine id linked to the meter
    - net head (no hard-coded default)
    - efficiency curve points (q_ls, eta)
    """
    params = _get_turbina_params_for_misuratore(id_misuratore)
    if not params:
        return None

    turbina_id = params[0]
    salto_netto_m = _safe_float(params[1])
    salto_nominale_m = _safe_float(params[2])
    head_m = salto_netto_m if salto_netto_m is not None else salto_nominale_m
    if head_m is None or head_m <= 0:
        return None

    q_points_ls, eta_points = _get_turbina_curve_points_by_id(turbina_id)
    if not q_points_ls or not eta_points:
        return None

    return {
        "turbina_id": turbina_id,
        "head_m": head_m,
        "q_points_ls": q_points_ls,
        "eta_points": eta_points,
    }


def _compute_eta_potenza(flow_ls_avg, params):
    (
        turbina_id,
        salto_netto_m,
        salto_nominale_m,
        eta0,
        eta_max,
        x0,
        aL,
        aR,
        kL,
        kR,
        q_min_ls,
        q_max_ls,
    ) = params

    head_m = float(salto_netto_m) if salto_netto_m is not None else float(salto_nominale_m or 0)
    denom_q = float(q_max_ls - q_min_ls) if q_max_ls is not None and q_min_ls is not None else 0.0
    if denom_q <= 0:
        return {
            "eta": None,
            "power_kw": None,
            "head_m": head_m if head_m > 0 else None,
            "x": None,
            "turbina_id": turbina_id,
        }

    x = (flow_ls_avg - float(q_min_ls)) / denom_q
    x = max(0.0, min(1.0, x))

    if x <= float(x0):
        eta = float(eta0) + (float(eta_max) - float(eta0)) * (
            1 - float(aL) * abs(x - float(x0)) ** float(kL)
        )
    else:
        eta = float(eta0) + (float(eta_max) - float(eta0)) * (
            1 - float(aR) * abs(x - float(x0)) ** float(kR)
        )

    q_m3s = flow_ls_avg / 1000.0
    power_kw = 9.81 * head_m * q_m3s * eta if head_m > 0 else None
    if power_kw is not None:
        power_kw = max(0.0, power_kw)

    return {
        "eta": eta,
        "power_kw": power_kw,
        "head_m": head_m if head_m > 0 else None,
        "x": x,
        "turbina_id": turbina_id,
    }


@login_required
def rendimento_potenza_api(request):
    id_misuratore, error = validate_id_misuratore(request.GET.get("id_misuratore"))
    if error:
        return JsonResponse({"error": error}, status=400)

    latest_ts, flow_ls_avg = _get_latest_flow_avg_30m(id_misuratore)
    if latest_ts is None:
        return JsonResponse(
            {
                "flow_ls_avg_30m": None,
                "eta": None,
                "power_kw": None,
                "head_m": None,
                "is_stale": True,
            }
        )
    if latest_ts < (timezone.now() - timedelta(minutes=30)):
        return JsonResponse(
            {
                "flow_ls_avg_30m": None,
                "eta": None,
                "power_kw": None,
                "head_m": None,
                "is_stale": True,
            }
        )

    params = _get_turbina_params_for_misuratore(id_misuratore)
    if not params:
        return JsonResponse(
            {
                "flow_ls_avg_30m": float(flow_ls_avg),
                "eta": None,
                "power_kw": None,
                "head_m": None,
                "is_stale": False,
            }
        )

    flow_ls_avg = float(flow_ls_avg)
    computed = _compute_eta_potenza(flow_ls_avg, params)

    return JsonResponse(
        {
            "flow_ls_avg_30m": flow_ls_avg,
            "eta": computed["eta"],
            "power_kw": computed["power_kw"],
            "head_m": computed["head_m"],
            "x": computed["x"],
            "turbina_id": computed["turbina_id"],
            "is_stale": False,
        }
    )


@login_required
def curva_di_rendimento_turbina(request, nome_turbina):
    """
    Return dataset as {"curve_points": {"x": [...], "eta": [...]}} 
    where x and eta are lists of floats corresponding to the curve points 
    for the turbine with the given name.
    """
    if(nome_turbina is None or len(nome_turbina.strip()) == 0):
        return JsonResponse({"error": "nome_turbina is required"}, status=400)
    nome_turbina = nome_turbina.strip()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT x, eta
            FROM hydro.tab_turbina_curve_points as tbcp
            JOIN hydro.tab_tipologia_turbina as ttt ON tbcp.id_turbina = ttt.id
            WHERE ttt.nome = %s
            """,
            [nome_turbina]
        )
        rows = cursor.fetchall() # dovrebbero essere ~400 righe per ogni turbina
    
    if not rows:  # Check first, process after
        return JsonResponse({"error": f"No curve points found for this turbine with name {nome_turbina}"}, status=404)
    
    x = [float(row[0]) for row in rows]
    eta = [float(row[1]) for row in rows]
    return JsonResponse({"curve_points": {"x": x, "eta": eta}}, status=200)
    
    
@login_required
def test_canvas(request, nome_tipologia_turbina):
    return render(request, "portale/includes/test_canvas.html", {
        "title": f"Test Canvas - {nome_tipologia_turbina}",
        "nome_turbina": nome_tipologia_turbina  # Pass actual parameter value
        })
    


@login_required
def misuratori_index(request): 
    misuratori = tab_misuratori.objects.all()
    context = {
        "misuratori": misuratori,
        "title": "Hydro 3.0",
    }
    return render(request, "portale/misuratori_index.html", context)


