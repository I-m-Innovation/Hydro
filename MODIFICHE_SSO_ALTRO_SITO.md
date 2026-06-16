# Modifiche SSO Portale Impianti

Questo file riguarda solo il sito esterno Portale Impianti.

Eye-Q resta l'unico gestionale utenti. Portale Impianti non deve avere login, registrazione o permessi propri per decidere chi puo' entrare.

Nel sito esterno puo' restare un `auth.User` locale solo per sessione Django, log, autore dei record e foreign key gia' esistenti.

## Dati SSO

Eye-Q invia un token firmato con questi valori:

```text
aud = portale_impianti
page = portale_impianti
iss = eyeq
```

La variabile ambiente obbligatoria nel sito Portale Impianti e':

```text
EYEQ_PORTALE_IMPIANTI_SSO_SECRET=<SECRET_CONDIVISA>
```

La stessa secret deve essere impostata anche nel progetto Eye-Q.

## Settings da aggiungere

Versione semplice: solo la secret arriva da variabile ambiente.

```python
EYEQ_PORTALE_IMPIANTI_ENTRY_URL = "http://127.0.0.1:8000/portale-impianti/"
EYEQ_PORTALE_IMPIANTI_SSO_SECRET = os.environ.get("EYEQ_PORTALE_IMPIANTI_SSO_SECRET", "").strip()
EYEQ_PORTALE_IMPIANTI_SSO_SALT = "eyeq-portale-impianti-sso"
EYEQ_PORTALE_IMPIANTI_SSO_MAX_AGE_SECONDS = 60
EYEQ_PORTALE_IMPIANTI_SSO_ISSUER = "eyeq"
EYEQ_PORTALE_IMPIANTI_SSO_AUDIENCE = "portale_impianti"
```

## Route da avere

Nel `urls.py` del Portale Impianti:

```python
path("", views.sso_required, name="login"),
path("login/", views.sso_required, name="login_page"),
path("sso-login/", views.sso_login, name="sso_login"),
path("logout/", views.logout_view, name="logout"),
```

Se il sito e' montato sotto `/portale/`, queste route devono stare sotto quel prefisso.

## Login locale da rimuovere

Cerca e rimuovi/adatta:

```text
UserCreationForm
register/
def register
Permission
has_perm(...)
user_permissions.add(...)
```

Le view operative del portale devono restare protette con `@login_required`.

## View SSO/logout

Nel `views.py` del Portale Impianti aggiungi questi import se mancano:

```python
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
```

Poi aggiungi queste funzioni.

Nota: cambia `reverse("home")` se la home del Portale Impianti ha un nome diverso.

```python
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

    next_path = _safe_local_redirect(request, request.GET.get("next"), reverse("home"))
    separator = "&" if "?" in entry_url else "?"
    return redirect(f"{entry_url}{separator}{urlencode({'next': next_path})}")


@never_cache
def sso_required(request):
    if request.user.is_authenticated:
        return redirect("home")
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

    next_url = _safe_local_redirect(request, payload.get("next") or request.GET.get("next"), reverse("home"))
    return redirect(next_url)


def logout_view(request):
    logout(request)
    return redirect("login")
```

## Test minimi

- token valido crea sessione locale
- token senza `page = portale_impianti` riceve 403
- token con `aud` sbagliata riceve 403
- token con `iss` sbagliato riceve 403
- token scaduto rimanda a Eye-Q
- utente non autenticato viene rimandato a Eye-Q

## Cause tipiche di 403

1. Secret non impostata.
2. Secret diversa tra Eye-Q e Portale Impianti.
3. Server Django non riavviato dopo la variabile ambiente.
4. Salt diverso.
5. Issuer diverso.
6. `aud` o `page` diversi da `portale_impianti`.
7. Eye-Q sta puntando all'URL sbagliato del Portale Impianti.
